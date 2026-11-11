# -*- coding: utf-8 -*-
"""DrissionPage 版爬虫：抓取 https://mitadmissions.org/blogs/ 的文章列表和详情，输出 CSV。

和 Playwright 版抓同样的字段、同样的页面，只是换成 DrissionPage 的 API：
- 浏览器接管：ChromiumPage + ChromiumOptions
- 等待：page.wait.doc_loaded() / 轮询元素文本
- 解析：page.eles() 取卡片、ele().text 取文本、ele().attrs 取图片地址

一个细节：DrissionPage 的 element.text 会连 display:none 的元素一起取，
而本站正文里的脚注是隐藏元素（鼠标悬浮才显示），直接用 .text 会把脚注内容混进正文。
所以正文改用 run_js('return this.innerText')，和浏览器里“可见文本”保持一致。

运行：python crawler_drissionpage.py [--pages 1] [--headed]
"""

from __future__ import annotations

import argparse
import re
import time

from DrissionPage import ChromiumPage, ChromiumOptions

from common.config import (
    COUNT_WAIT_MS,
    CSV_HEADERS,
    DRISSIONPAGE_CSV,
    LIST_URL,
    NAV_TIMEOUT_MS,
    PAGE_URL_TPL,
    PAGES_DEFAULT,
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
    pick_image_src,
    strip_author_suffix,
    unique_image_srcs,
)

# 取元素可见文本。三个坑一起处理：
# 1) 隐藏元素（例如脚注）也会被 .text 取到，所以用 innerText；
# 2) 相册的 “Previous / Next” 按钮带 .visually-hidden 的文字，innerText 会算进来，先删掉；
# 3) WordPress 的 emoji 脚本把 emoji 换成了 <img class="emoji" alt="🎪">，
#    innerText 读不到 alt，emoji 会凭空消失，所以先按 alt 还原成文本再读。
_VISIBLE_TEXT_JS = """
this.querySelectorAll('.visually-hidden, .carousel-nav__button, .flickity-button, .flickity-page-dots')
  .forEach(node => node.remove());
this.querySelectorAll('img.emoji, img.wp-smiley').forEach(im =>
    im.replaceWith(document.createTextNode(im.getAttribute('alt') || '')));
return this.innerText;
"""
# 正文里的图片地址：相册图是懒加载的，真实地址在 data-flickity-lazyload-src 上
# 排除 img.emoji / img.wp-smiley —— 那是 emoji 转成的图片，不算文章配图
_IMG_ATTRS = ("data-flickity-lazyload-src", "data-src", "data-lazy-src", "src")
_SEL_REAL_IMG = "img:not(.emoji):not(.wp-smiley)"


def _build_page(headless: bool) -> ChromiumPage:
    """启动（无头）Chrome。auto_port 让每个进程用独立端口和临时用户目录，避免抢已有浏览器。"""
    options = ChromiumOptions().auto_port()
    options.headless(headless)
    options.set_argument("--disable-gpu")
    options.set_argument("--no-first-run")
    options.set_argument("--disable-blink-features=AutomationControlled")
    options.set_user_agent(USER_AGENT)
    options.set_timeouts(base=5, page_load=NAV_TIMEOUT_MS / 1000, script=30)

    page = ChromiumPage(options)
    # eager：DOMContentLoaded 就返回，不等图片等资源全部加载完
    page.set.load_mode.eager()
    # 这里故意不做 set.blocked_urls：实测屏蔽图片后 Disqus 的 count.js 不再发起
    # 计数请求，评论数就渲染不出来（Playwright 侧用 route.abort 没这个问题）
    return page


def _wait_comment_counts(page: ChromiumPage, timeout_ms: int = COUNT_WAIT_MS) -> None:
    """轮询等 Disqus count.js 把 “N comments” 写进占位 <a>，超时交给接口兜底。"""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        anchors = page.eles("css:" + SEL_CARD_COMMENT)
        if any((a.text or "").strip() for a in anchors):
            return
        page.wait(0.5)
    print("  [warn] Disqus 评论数未在页面渲染，将使用接口兜底")


def _read_text(element, default: str = "") -> str:
    """取元素可见文本并还原 emoji；元素为 None 时返回默认值。"""
    if element is None:
        return default
    try:
        value = element.run_js(_VISIBLE_TEXT_JS)
    except Exception:
        # 极端情况下 JS 执行失败，退回 DrissionPage 原生的 .text
        value = element.text
    return value if isinstance(value, str) else default


def collect_cards(page: ChromiumPage, pages: int) -> list[dict]:
    """遍历列表页（支持分页），返回文章卡片信息。"""
    cards: list[dict] = []
    for page_no in range(1, pages + 1):
        url = LIST_URL if page_no == 1 else PAGE_URL_TPL.format(page=page_no)
        print(f"[DrissionPage] 打开列表页 {url}")
        page.get(url, retry=2, interval=1, timeout=NAV_TIMEOUT_MS / 1000)
        page.wait.doc_loaded(timeout=30)
        page.ele("css:" + SEL_CARD, timeout=WAIT_TIMEOUT_MS / 1000)
        _wait_comment_counts(page)

        elements = page.eles("css:" + SEL_CARD)
        print(f"  本页共 {len(elements)} 篇文章")
        for card in elements:
            link = card.ele("css:" + SEL_CARD_LINK, timeout=2)
            title_el = card.ele("css:" + SEL_CARD_TITLE, timeout=2)
            sub_el = card.ele("css:" + SEL_CARD_SUB, timeout=1)
            author_el = card.ele("css:" + SEL_CARD_AUTHOR, timeout=2)
            date_el = card.ele("css:" + SEL_CARD_DATE, timeout=2)
            anchor = card.ele("css:" + SEL_CARD_COMMENT, timeout=2)

            # 标题里可能有 emoji（WordPress 会转成 <img>），用 _read_text 还原
            title = clean_text(_read_text(title_el))
            subtitle = clean_text(_read_text(sub_el))
            if subtitle:  # 卡片上的副标题要和主标题拼起来才是完整标题
                title = f"{title} {subtitle}".strip()

            cards.append(
                {
                    "url": (link.attr("href") or "") if link else "",
                    "title": title,
                    "author": clean_text(author_el.text if author_el else ""),
                    "date_text": clean_text(date_el.text if date_el else ""),
                    "ident": (anchor.attr("data-disqus-identifier") or "") if anchor else "",
                    "comment_text": clean_text(anchor.text if anchor else ""),
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


def _image_srcs(body) -> list[str]:
    """取正文里所有图片的真实地址（.attrs 一次拿全属性，比逐个 attr 快）。"""
    srcs: list[str] = []
    for img in body.eles("css:" + _SEL_REAL_IMG):
        try:
            attrs = img.attrs or {}
        except Exception:
            attrs = {name: img.attr(name) for name in _IMG_ATTRS}
        srcs.append(pick_image_src(attrs))
    return srcs


def parse_article(page: ChromiumPage, card: dict) -> dict:
    """打开文章页，取标题、作者、日期、正文和图片。"""
    page.get(card["url"], retry=2, interval=1, timeout=NAV_TIMEOUT_MS / 1000)
    page.wait.doc_loaded(timeout=30)
    title_el = page.ele("css:" + SEL_ART_TITLE, timeout=WAIT_TIMEOUT_MS / 1000)

    # 文章页 h1 形如 “Something to believe in by Janet G. '27”，作者在子元素里，需要摘掉
    author_el = page.ele("css:" + SEL_ART_AUTHOR, timeout=2)
    author_label = clean_text(author_el.text if author_el else "")
    title = strip_author_suffix(clean_text(_read_text(title_el)), author_label)
    sub_el = page.ele("css:" + SEL_ART_SUB, timeout=1)
    subtitle = clean_text(_read_text(sub_el))
    if subtitle:
        title = f"{title} {subtitle}".strip()
    title = title or card["title"]

    author = re.sub(r"^by\s+", "", author_label, flags=re.I).strip() or card["author"]

    # 日期优先取 <time datetime="2026-11-09T00:00:00-05:00"> 里的 ISO 值
    time_el = page.ele("css:" + SEL_ART_DATE, timeout=2)
    iso = date_to_iso(time_el.attr("datetime")) if time_el else ""
    time_value = iso or card["date_text"]

    # 正文：.article__body 是标准容器，个别模板缺失时退回 .article__content
    body = page.ele("css:" + SEL_ART_BODY, timeout=10)
    if body is None:
        body = page.ele("css:" + SEL_ART_BODY_FALLBACK, timeout=5)
    content = clean_content(_read_text(body))
    images = unique_image_srcs(_image_srcs(body)) if body is not None else []

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
    page = _build_page(headless)
    try:
        cards = collect_cards(page, pages)
        resolve_comment_counts(cards)
        total = len(cards)
        for idx, card in enumerate(cards, start=1):
            try:
                row = parse_article(page, card)
            except Exception as exc:   # 单篇失败不影响整批，日志里能看出来
                print(f"  [{idx}/{total}] 解析失败，已跳过：{type(exc).__name__}: {exc}")
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
        page.quit()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="DrissionPage 爬取 MIT Admissions 博客")
    parser.add_argument("--pages", type=int, default=PAGES_DEFAULT, help="抓取列表页数，默认 1")
    parser.add_argument("--headed", action="store_true", help="显示浏览器窗口（调试用）")
    args = parser.parse_args()

    started = time.time()
    rows = crawl(pages=args.pages, headless=not args.headed)
    out = write_csv(DRISSIONPAGE_CSV, rows, CSV_HEADERS)
    print(f"[DrissionPage] 完成，{len(rows)} 条记录 -> {out}（耗时 {time.time() - started:.1f}s）")


if __name__ == "__main__":
    main()
