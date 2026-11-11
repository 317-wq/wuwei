# -*- coding: utf-8 -*-
"""公共配置：站点地址、CSS 选择器、CSV 表头、输出路径。

Playwright 和 DrissionPage 两套实现共用这里的常量，
保证两边抓的是同一批页面、同一批字段，结果可以直接对比。
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# 站点地址
# ---------------------------------------------------------------------------
BASE_URL = "https://mitadmissions.org"
LIST_URL = "https://mitadmissions.org/blogs/"
# 列表分页规则：第 2 页起为 /blogs/page/2/
PAGE_URL_TPL = "https://mitadmissions.org/blogs/page/{page}/"

# 伪装成普通 Chrome，避免被站点当成脚本/无头浏览器而返回阉割页面
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# 输出的 CSV
# ---------------------------------------------------------------------------
CSV_HEADERS = [
    "Title",
    "Author",
    "Comment Count",
    "Time",
    "Article Content",
    "Images In Article",
]

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "output"
PLAYWRIGHT_CSV = OUTPUT_DIR / "playwright_blogs.csv"
DRISSIONPAGE_CSV = OUTPUT_DIR / "drissionpage_blogs.csv"
MERGED_CSV = OUTPUT_DIR / "merged_blogs.csv"

# ---------------------------------------------------------------------------
# 抓取参数
# ---------------------------------------------------------------------------
PAGES_DEFAULT = 1          # 默认只抓列表第一页（16 篇）
NAV_TIMEOUT_MS = 60_000    # 页面跳转超时
WAIT_TIMEOUT_MS = 30_000   # 等待关键元素出现
COUNT_WAIT_MS = 15_000     # 等待 Disqus 评论数脚本把数字填进 DOM
REQUEST_INTERVAL = 0.5     # 两篇文章之间的礼貌间隔（秒）

# ---------------------------------------------------------------------------
# 选择器：列表页
# ---------------------------------------------------------------------------
SEL_CARD = "article.tease--post"          # 单张文章卡片
SEL_CARD_LINK = "a.post-tease__h__link"   # 卡片标题链接（文章 URL）
SEL_CARD_TITLE = ".post-tease__title"     # 主标题
SEL_CARD_SUB = ".post-tease__subtitle"    # 副标题（可能没有）
SEL_CARD_AUTHOR = ".post-tease__meta-item--author a"
SEL_CARD_DATE = ".tease__meta-item--date"
# 评论数：Disqus 用这个带 data-disqus-identifier 的 <a> 占位，
# 页面加载后由 count.js 把 “N comments” 写进它的文本
SEL_CARD_COMMENT = "a[data-disqus-identifier]"

# ---------------------------------------------------------------------------
# 选择器：文章详情页
# ---------------------------------------------------------------------------
SEL_ART_TITLE = "h1.page-topper__title"
SEL_ART_AUTHOR = ".page-topper__title__name"   # h1 里的 “by 某某”
SEL_ART_SUB = "p.page-topper__sub"
SEL_ART_DATE = "time.page-topper__date"        # 带 datetime 属性，形如 2026-11-09T00:00:00-05:00
SEL_ART_BODY = ".article__body"                # 正文容器
SEL_ART_BODY_FALLBACK = ".article__content"    # 少数模板没有 .article__body 时兜底

# 正文里取图片地址时依次尝试的属性：
# 站点相册（flickity）的图片是懒加载的，真实地址放在 data-flickity-lazyload-src 里
IMG_ATTRS = (
    "data-flickity-lazyload-src",
    "data-src",
    "data-lazy-src",
    "src",
)

# 这些资源对“文本 + 图片数量”没有帮助，Playwright 里直接中断请求以加速
BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}
