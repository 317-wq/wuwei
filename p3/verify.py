# -*- coding: utf-8 -*-
"""对比两份 CSV 的结果，确认两个框架抓到的内容一致。

用法：
    python verify.py
    python verify.py --pw output/playwright_blogs.csv --dp output/drissionpage_blogs.csv
"""

from __future__ import annotations

import argparse
import csv
import sys

from common.config import DRISSIONPAGE_CSV, PLAYWRIGHT_CSV
from common.text import normalize_for_compare

# 需要逐字段比对的列（正文单独用“忽略排版差异”的方式比）
_SCALAR_FIELDS = ("Author", "Comment Count", "Time", "Images In Article")


def load_rows(path) -> list[dict]:
    """读 CSV（utf-8-sig，兼容 Excel 另存过的文件）。"""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def compare(pw_path=PLAYWRIGHT_CSV, dp_path=DRISSIONPAGE_CSV, verbose: bool = True) -> bool:
    """逐行对比两份结果，返回是否完全一致。"""
    left = load_rows(pw_path)
    right = load_rows(dp_path)
    if verbose:
        print(f"Playwright : {len(left)} 行  <- {pw_path}")
        print(f"DrissionPage: {len(right)} 行  <- {dp_path}")

    ok = len(left) == len(right)
    if not ok and verbose:
        print(f"  [差异] 行数不一致：{len(left)} vs {len(right)}")

    for idx, (a, b) in enumerate(zip(left, right), start=1):
        if a["Title"] != b["Title"]:
            print(f"  [{idx}] Title 不一致：{a['Title']!r} != {b['Title']!r}")
            ok = False
        for field in _SCALAR_FIELDS:
            va, vb = (a.get(field) or "").strip(), (b.get(field) or "").strip()
            if va != vb:
                print(f"  [{idx}] {field} 不一致：{va!r} != {vb!r}")
                ok = False
        # 正文可能因为框架换行处理不同而排版不同，压平空白后再比
        ca = normalize_for_compare(a.get("Article Content") or "")
        cb = normalize_for_compare(b.get("Article Content") or "")
        if ca != cb:
            print(f"  [{idx}] Article Content 不一致：{len(ca)} vs {len(cb)} 字符（{a['Title']!r}）")
            ok = False

    if verbose:
        print("结果一致 ✅" if ok else "存在差异 ❌（见上）")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="对比 Playwright / DrissionPage 两份 CSV")
    parser.add_argument("--pw", default=str(PLAYWRIGHT_CSV))
    parser.add_argument("--dp", default=str(DRISSIONPAGE_CSV))
    args = parser.parse_args()
    sys.exit(0 if compare(args.pw, args.dp) else 1)


if __name__ == "__main__":
    main()
