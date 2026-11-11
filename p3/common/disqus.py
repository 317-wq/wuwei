# -*- coding: utf-8 -*-
"""Disqus 评论数兜底接口。

列表页上的 “N comments” 是 Disqus 的 count.js 在页面加载后用 JS 写进去的，
如果脚本被网络/广告拦截器挡住，DOM 里就只剩一个空的 <a>。
Disqus 的 count-data.js 支持一次批量查询，返回 JSONP 形式的数据，用它兜底：

    https://mitadmissions.disqus.com/count-data.js?1=<ident1>&1=<ident2>

其中 ident 取自列表页 <a data-disqus-identifier="..."> 的值。
"""

from __future__ import annotations

import json
import re

import requests

from common.config import USER_AGENT
from common.text import clean_text

COUNT_API = "https://mitadmissions.disqus.com/count-data.js"
# 从 JSONP 中抠出 displayCount({...}) 的 JSON 部分
_CALLBACK_RE = re.compile(r"displayCount\(\s*(\{.*\})\s*\)", re.S)


def fetch_comment_counts(identifiers: list[str], chunk_size: int = 20, timeout: int = 20) -> dict[str, int]:
    """批量查询评论数，返回 {identifier: 评论数}；查询失败时返回空字典，不影响主流程。"""
    result: dict[str, int] = {}
    idents = [i for i in identifiers if i]
    for start in range(0, len(idents), chunk_size):
        chunk = idents[start:start + chunk_size]
        try:
            resp = requests.get(
                COUNT_API,
                params=[("1", ident) for ident in chunk],
                headers={
                    "User-Agent": USER_AGENT,
                    "Referer": "https://mitadmissions.org/blogs/",
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            match = _CALLBACK_RE.search(resp.text)
            if not match:
                continue
            payload = json.loads(match.group(1))
            for item in payload.get("counts", []):
                ident = clean_text(item.get("id"))
                if ident:
                    result[ident] = int(item.get("comments", 0))
        except (requests.RequestException, ValueError, TypeError):
            # 兜底接口挂了也无所谓，调用方会用 0 补齐
            continue
    return result
