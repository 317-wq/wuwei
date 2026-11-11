"""传输协议编码：把统一的事件三元组编码成 SSE 或 NDJSON 帧。

SSE 帧格式（每个字段一行，事件之间用空行分隔）::

    id: 3
    event: token
    data: {"index":2,"delta":"流"}

    retry: 3000

注意：``data`` 字段的值里不能出现未转义的换行，否则会被拆成多个 data 行；
这里统一用 JSON（换行会被转义成 ``\\n``），并按行兜底拆分。
"""

from __future__ import annotations

import json
from typing import Any


def sse_event(event: str, data: dict[str, Any], event_id: int | None = None) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    lines: list[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.extend(f"data: {line}" for line in payload.split("\n"))
    return "\n".join(lines) + "\n\n"


def sse_retry(milliseconds: int) -> str:
    """告诉浏览器断线后多久重连；只在流开头发一次。"""
    return f"retry: {milliseconds}\n\n"


def ndjson_event(event: str, data: dict[str, Any]) -> str:
    """NDJSON：一行一个完整 JSON，客户端按换行切分即可。"""
    return json.dumps({"event": event, "data": data}, ensure_ascii=False, separators=(",", ":")) + "\n"
