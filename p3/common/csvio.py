# -*- coding: utf-8 -*-
"""CSV 输出。"""

from __future__ import annotations

import csv
from pathlib import Path

from common.config import CSV_HEADERS


def write_csv(path: Path, rows: list[dict], headers: list[str] | None = None) -> Path:
    """按固定表头写 CSV。

    用 utf-8-sig 编码：带 BOM，Excel 直接双击打开不会中文/emoji 乱码；
    字段里含换行（正文有多段），统一交给 QUOTE_ALL 加引号，不会串行。
    """
    headers = headers or CSV_HEADERS
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        # extrasaction="ignore"：行里如果有额外字段（比如分页序号）不写进 CSV
        writer = csv.DictWriter(fh, fieldnames=headers, extrasaction="ignore", quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)
    return path
