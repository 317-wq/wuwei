# -*- coding: utf-8 -*-
"""Playwright 版爬虫：抓取 https://mitadmissions.org/blogs/ 的文章列表和详情，输出 CSV。

思路：
1. 用 Chromium 打开列表页，逐张卡片取 标题 / 作者 / 日期 / 评论数 / 链接；
   评论数是 Disqus 的 count.js 在页面加载后写进 DOM 的，必须用真实浏览器才能拿到；
2. 逐篇打开文章页，取正文纯文本和正文里的图片；
3. 结果写入 output/playwright_blogs.csv。

运行：python crawler_playwright.py [--pages 1] [--headed]
"""

from __future__ import annotations

import argparse
import re
import time
from typing import Any

from playwright.sync_api import Page, TimeoutError as PWTimeoutError, sync_playwright

from common.config import (
    BLOCKED_RESOURCE_TYPES,
    COUNT_WAIT_MS,
    CSV_HEADERS,
    LIST_URL,
    NAV_TIMEOUT_MS,
    PAGE_URL_TPL,
    PAGES_DEFAULT,
    PLAYWRIGHT_CSV,
    REQUEST_INTERVAL,
    SEL_ART_AUTHOR,
    SEL_ART_BODY,
    SEL_ART_BODY_FALLBACK,
    SEL_ART_DATE,
    SEL_ART_SUB,
    SEL_ART_TITLE,
    SEL_CARD,
    SEL_CARD_AUTHOR,
    SEL_CARD_COMMENT,
    SEL_CARD_DATE,
    SEL_CARD_LINK,
    SEL_CARD_SUB,
    SEL_CARD_TITLE,
    USER_AGENT,
    WAIT_TIMEOUT_MS,
)
from common.csvio import write_csv
from common.disqus import fetch_comment_counts
from common.text import (
    clean_content,
    clean_text,
    date_to_iso,
    parse_comment_count,
    strip_author_suffix,
    unique_image_srcs,
)

# 在页面里执行：取正文所有 <img> 的真实地址（相册图是懒加载的，src 可能为空）
# 排除 img.emoji / img.wp-smiley —— 那是 WordPress 把 emoji 转成的图片，不是文章配图
_IMG_SRC_JS = """
(el) => Array.from(el.querySelectorAll('img:not(.emoji):not(.wp-smiley)')).map(im =>
    im.getAttribute('data-flickity-lazyload-src') ||
    im.getAttribute('data-src') ||
    im.getAttribute('data-lazy-src') ||
    im.getAttribute('src') || '')
"""

# 取元素可见文本。几个坑一起处理：
# 1) 隐藏元素（例如脚注 span）不算正文，innerText 天然只返回可见文本；
# 2) 相册的 “Previous / Next” 按钮带 .visually-hidden 的文字，innerText 会把它算进来，先删掉；
# 3) WordPress 的表情脚本会把 emoji 转成 <img class="emoji" alt="🎪">，
#    这时 innerText 读不到 emoji，先把图片按 alt 还原成文本再读。
# 这些操作都放在同一次求值里，避免中途被页面脚本改回去。
_VISIBLE_TEXT_JS = """
(el) => {
  el.querySelectorAll('.visually-hidden, .carousel-nav__button, .flickity-button, .flickity-page-dots')
    .forEach(node => node.remove());
  el.querySelectorAll('img.emoji, img.wp-smiley').forEach(im =>
      im.replaceWith(document.createTextNode(im.getAttribute('alt') || '')));
  return el.innerText;
}
"""

# 等 Disqus 把评论数写进占位 <a>：只要有一个非空就说明脚本已经跑起来了
_COUNT_READY_JS = """
() => Array.from(document.querySelectorAll('a[data-disqus-identifier]'))
        .some(a => (a.textContent || '').trim() !== '')
"""


def _block_heavy_assets(route: Any) -> None:
    """中断图片 / 字体 / 视频请求：只为提速，不影响 DOM（图片数量仍按 <img> 标签统计）。"""
    if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
        route.abort()
    else:
        route.continue_()


def _text_with_emoji(locator: Any, default: str = "") -> str:
    """取元素可见文本（顺带还原 emoji 图片）；元素不存在或超时返回默认值。"""
    if locator.count() == 0:
        return default
    try:
        return locator.first.evaluate(_VISIBLE_TEXT_JS).strip()
    except PWTimeoutError:
        return default


def _wait_comment_counts(page: Page) -> None:
    """等 Disqus count.js 渲染评论数，超时就交给后面的接口兜底。"""
    try:
        page.wait_for_function(_COUNT_READY_JS, timeout=COUNT_WAIT_MS)
    except PWTimeoutError:
        print("  [warn] Disqus 评论数未在页面渲染，将使用接口兜底")


def collect_cards(page: Page, pages: int) -> list[dict]:
    """遍历列表页（支持分页），返回文章卡片信息。"""
    cards: list[dict] = []
    for page_no in range(1, pages + 1):
        url = LIST_URL if page_no == 1 else PAGE_URL_TPL.format(page=page_no)
        print(f"[Playwright] 打开列表页 {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
        page.wait_for_selector(SEL_CARD, timeout=WAIT_TIMEOUT_MS)
        _wait_comment_counts(page)

        locator = page.locator(SEL_CARD)
        total = locator.count()
        print(f"  本页共 {total} 篇文章")
        for i in range(total):
            card = locator.nth(i)
            title = clean_text(_text_with_emoji(card.locator(SEL_CARD_TITLE)))
            subtitle = clean_text(_text_with_emoji(card.locator(SEL_CARD_SUB)))
            if subtitle:  # 卡片上的副标题要和主标题拼起来才是完整标题
                title = f"{title} {subtitle}".strip()

            anchor = card.locator(SEL_CARD_COMMENT).first
            cards.append(
                {
                    "url": card.locator(SEL_CARD_LINK).first.get_attribute("href") or "",
                    "title": title,
                    "author": clean_text(_text_with_emoji(card.locator(SEL_CARD_AUTHOR))),
                    "date_text": clean_text(_text_with_emoji(card.locator(SEL_CARD_DATE))),
                    # Disqus 的线程标识，接口兜底时要用
                    "ident": anchor.get_attribute("data-disqus-identifier") or "",
                    "comment_text": _text_with_emoji(anchor),
                }
            )
    return cards


def resolve_comment_counts(cards: list[dict]) -> None:
    """先用页面上渲染出来的数字；没有渲染出来的批量查 Disqus 接口补上。"""
    missing: list[dict] = []
    for card in cards:
        count = parse_comment_count(card["comment_text"])
        if count is None:
            missing.append(card)   # 空字符串：可能是 0 条，也可能是脚本没跑
        else:
            card["count"] = count

    if missing:
        print(f"  {len(missing)} 篇没有渲染出评论数，调用 Disqus count-data.js 兜底")
        counts = fetch_comment_counts([card["ident"] for card in missing])
        for card in missing:
            card["count"] = counts.get(card["ident"], 0)


def parse_article(page: Page, card: dict) -> dict:
    """打开文章页，取标题、作者、日期、正文和图片。"""
    page.goto(card["url"], wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    page.wait_for_selector(SEL_ART_TITLE, timeout=WAIT_TIMEOUT_MS)

    # 文章页 h1 形如 “Something to believe in by Janet G. '27”，作者在子元素里，需要摘掉
    author_label = _text_with_emoji(page.locator(SEL_ART_AUTHOR))
    title = strip_author_suffix(_text_with_emoji(page.locator(SEL_ART_TITLE)), author_label)
    subtitle = clean_text(_text_with_emoji(page.locator(SEL_ART_SUB)))
    if subtitle:
        title = f"{title} {subtitle}".strip()
    title = title or card["title"]

    author = re.sub(r"^by\s+", "", author_label, flags=re.I).strip() or card["author"]

    # 日期优先取 <time datetime="2026-11-09T00:00:00-05:00"> 里的 ISO 值，稳定且可排序
    time_node = page.locator(SEL_ART_DATE)
    iso = ""
    if time_node.count():
        iso = date_to_iso(time_node.first.get_attribute("datetime"))
    time_value = iso or card["date_text"]

    # 正文：.article__body 是标准容器，个别模板缺失时退回 .article__content
    body = page.locator(SEL_ART_BODY)
    if body.count() == 0:
        body = page.locator(SEL_ART_BODY_FALLBACK)
    content = clean_content(_text_with_emoji(body))
    images = unique_image_srcs(body.first.evaluate(_IMG_SRC_JS)) if body.count() else []

    return {
        "Title": title,
        "Author": author,
        "Comment Count": card.get("count", 0),
        "Time": time_value,
        "Article Content": content,
        "Images In Article": len(images),
    }


def crawl(pages: int = PAGES_DEFAULT, headless: bool = True) -> list[dict]:
    """入口：返回符合 CSV 表头的行列表。"""
    rows: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-gpu", "--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
        )
        context.route("**/*", _block_heavy_assets)
        page = context.new_page()
        page.set_default_timeout(WAIT_TIMEOUT_MS)
        try:
            cards = collect_cards(page, pages)
            resolve_comment_counts(cards)
            total = len(cards)
            for idx, card in enumerate(cards, start=1):
                try:
                    row = parse_article(page, card)
                except PWTimeoutError as exc:
                    # 单篇超时不影响整批，先记一条空正文，日志里能看出来
                    print(f"  [{idx}/{total}] 解析超时，已跳过：{exc}")
                    row = {
                        "Title": card["title"],
                        "Author": card["author"],
                        "Comment Count": card.get("count", 0),
                        "Time": card["date_text"],
                        "Article Content": "",
                        "Images In Article": 0,
                    }
                rows.append(row)
                print(f"  [{idx}/{total}] {row['Title'][:50]} | 评论 {row['Comment Count']} | 图片 {row['Images In Article']} | 正文 {len(row['Article Content'])} 字符")
                time.sleep(REQUEST_INTERVAL)
        finally:
            browser.close()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Playwright 爬取 MIT Admissions 博客")
    parser.add_argument("--pages", type=int, default=PAGES_DEFAULT, help="抓取列表页数，默认 1")
    parser.add_argument("--headed", action="store_true", help="显示浏览器窗口（调试用）")
    args = parser.parse_args()

    started = time.time()
    rows = crawl(pages=args.pages, headless=not args.headed)
    out = write_csv(PLAYWRIGHT_CSV, rows, CSV_HEADERS)
    print(f"[Playwright] 完成，{len(rows)} 条记录 -> {out}（耗时 {time.time() - started:.1f}s）")


if __name__ == "__main__":
    main()
