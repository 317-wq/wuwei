# -*- coding: utf-8 -*-
"""一键运行两个爬虫，输出两份 CSV + 一份合并 CSV，最后自动对比。

用法：
    python run_all.py            # 各抓列表第 1 页
    python run_all.py --pages 2  # 各抓 2 页
"""

from __future__ import annotations

import argparse
import time

from common.config import (
    CSV_HEADERS,
    DRISSIONPAGE_CSV,
    MERGED_CSV,
    PAGES_DEFAULT,
    PLAYWRIGHT_CSV,
)
from common.csvio import write_csv
from verify import compare

import crawler_drissionpage
import crawler_playwright


def main() -> None:
    parser = argparse.ArgumentParser(description="用 Playwright 和 DrissionPage 各跑一遍并对比")
    parser.add_argument("--pages", type=int, default=PAGES_DEFAULT, help="抓取列表页数，默认 1")
    parser.add_argument("--headed", action="store_true", help="显示浏览器窗口（调试用）")
    args = parser.parse_args()
    headless = not args.headed
    started = time.time()

    print("=" * 70)
    pw_rows = crawler_playwright.crawl(pages=args.pages, headless=headless)
    write_csv(PLAYWRIGHT_CSV, pw_rows)
    print(f"-> {PLAYWRIGHT_CSV}")

    print("=" * 70)
    dp_rows = crawler_drissionpage.crawl(pages=args.pages, headless=headless)
    write_csv(DRISSIONPAGE_CSV, dp_rows)
    print(f"-> {DRISSIONPAGE_CSV}")

    # 合并文件多一列 Source，方便人工核对两份结果
    merged = [{**row, "Source": "Playwright"} for row in pw_rows]
    merged += [{**row, "Source": "DrissionPage"} for row in dp_rows]
    write_csv(MERGED_CSV, merged, CSV_HEADERS + ["Source"])
    print(f"-> {MERGED_CSV}（{len(merged)} 行）")

    print("=" * 70)
    compare()

    print(f"总耗时 {time.time() - started:.1f}s")


if __name__ == "__main__":
    main()
