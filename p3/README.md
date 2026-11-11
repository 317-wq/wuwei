# MIT Admissions 博客爬虫（Playwright + DrissionPage）

用两套浏览器自动化框架抓取 <https://mitadmissions.org/blogs/> 的最新博客，
每条记录输出 6 个字段并写入 CSV：

| 字段 | 说明 |
| --- | --- |
| Title | 文章标题（主标题 + 副标题） |
| Author | 作者署名，如 `Janet G. '27` |
| Comment Count | Disqus 评论数（整数） |
| Time | 发布日期，ISO 格式 `2026-11-09` |
| Article Content | 正文纯文本（保留段落换行） |
| Images In Article | 正文配图数量（去重，不含 emoji 图片） |

默认抓列表第 1 页的 16 篇文章，`--pages N` 可以抓多页。

## 目录结构

```
p3/
├── crawler_playwright.py     # 方案一：Playwright
├── crawler_drissionpage.py   # 方案二：DrissionPage
├── run_all.py                # 一键跑两个方案 + 合并 + 自动对比
├── verify.py                 # 对比两份 CSV 是否一致
├── check_env.py              # 环境自检：解释器、依赖、浏览器是否就绪
├── requirements.txt
├── common/
│   ├── config.py             # 站点地址、CSS 选择器、表头、输出路径
│   ├── text.py               # 文本清洗、评论数解析、图片地址去重
│   ├── disqus.py             # Disqus 评论数兜底接口
│   └── csvio.py              # CSV 输出（utf-8-sig + QUOTE_ALL）
└── output/
    ├── playwright_blogs.csv
    ├── drissionpage_blogs.csv
    └── merged_blogs.csv      # 两份结果合在一起，多一列 Source
```

## 环境准备

```bash
pip install -r requirements.txt
python -m playwright install chromium   # Playwright 需要下载浏览器
```

DrissionPage 直接接管本机已安装的 Chrome（找不到时可用
`ChromiumOptions().set_browser_path(r"C:\...\chrome.exe")` 指定）。

## 运行

```bash
python check_env.py                      # 先自检：依赖装没装、浏览器能不能启动
python crawler_playwright.py            # 只跑 Playwright
python crawler_drissionpage.py          # 只跑 DrissionPage
python run_all.py                       # 两个都跑，并自动对比结果
python verify.py                        # 只对比 output/ 下现成的 CSV
```

调试时可以加 `--headed` 看到浏览器窗口。

> IDE 里出现 “无法解析导入 DrissionPage / playwright” 的波浪线，
> 基本是编辑器选中的解释器和实际运行的不是同一个（或语言服务器没刷新），
> 先执行 `python check_env.py` 确认，再在 IDE 里切到同一个解释器。

## 实现要点

1. **评论数必须用真实浏览器拿**：列表页的 “8 comments” 不是服务端渲染的，
   而是 Disqus 的 `count.js` 在页面加载后写进 `<a data-disqus-identifier>` 的，
   纯 HTTP 请求只能拿到一个空标签。
2. **评论数兜底**：如果 Disqus 脚本被挡住（网络/拦截器/加载时序），
   会用 `count-data.js?1=<identifier>` 批量查询补上，数字与页面完全一致；
   0 条评论的文章页面上本来就是空白，也由这条路径给出 `0`。
3. **emoji 的坑**：WordPress 的表情脚本会把 emoji 换成
   `<img class="emoji" alt="🎪">`，此时 `innerText` / `.text` 读不到它，
   标题和正文会“丢字符”。所以读文本前先按 `alt` 把 emoji 还原成文本；
   统计配图时则要把 `img.emoji` / `img.wp-smiley` 排除，否则 emoji 会被当成配图。
4. **页面噪声与隐藏元素**：正文容器里相册的 “Previous / Next” 按钮文字挂着
   `.visually-hidden`（视觉隐藏但 `innerText` 仍会带上），读正文前先删掉这些装饰节点；
   正文脚注是 `display:none`，`innerText` 天然跳过——而 DrissionPage 的 `.text`
   会把它们读出来，所以正文统一走 `innerText`。
5. **懒加载相册**：文章里的相册图片没有 `src`，真实地址在
   `data-flickity-lazyload-src` 上，按属性优先级取；同一张图会因相册克隆
   出现多次，按 URL 去重后计数。
6. **提速**：Playwright 侧拦截图片/字体/媒体请求（DOM 不变，`<img>` 仍在），
   并用 `domcontentloaded` 代替 `load`；DrissionPage 侧用 `eager` 加载模式。
   （DrissionPage 侧实测加了 `set.blocked_urls` 后 Disqus 不再发计数请求，
   评论数会拿不到，所以只保留了 eager。）
7. **编码**：CSV 用 `utf-8-sig`（Excel 直接打开不乱码）+ `QUOTE_ALL`
   （正文含换行，避免串行）。

## 结果校验

`verify.py` 会逐行比两份 CSV：标题、作者、评论数、日期、图片数必须完全相同，
正文在“压平空白”后比较（两个框架对换行的处理略有差异）。
