"""端到端接口测试：覆盖三种流式协议、非流式对照、参数校验和异常路径。

运行：``python -m pytest -q``
"""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app import service
from app.config import settings
from app.main import app
from app.models import ChatRequest

client = TestClient(app)


def parse_sse(text: str) -> list[dict]:
    """把 SSE 原始文本解析成事件列表（测试用简化版）。"""
    events: list[dict] = []
    for block in text.replace("\r\n", "\n").strip().split("\n\n"):
        if not block.strip():
            continue
        event = "message"
        event_id = None
        data_lines: list[str] = []
        for line in block.split("\n"):
            if not line or line.startswith(":"):
                continue
            field, _, value = line.partition(":")
            value = value[1:] if value.startswith(" ") else value
            if field == "event":
                event = value
            elif field == "data":
                data_lines.append(value)
            elif field == "id":
                event_id = int(value)
        if data_lines:
            events.append({"event": event, "data": json.loads("\n".join(data_lines)), "id": event_id})
    return events


def fast_payload(**overrides):
    """把延迟调成 0，让测试跑得快。"""
    payload = {
        "prompt": "介绍一下 FastAPI 的流式响应",
        "max_tokens": 20,
        "token_delay_ms": 0,
        "first_token_delay_ms": 0,
    }
    payload.update(overrides)
    return payload


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_index_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "FastAPI Streaming Demo" in response.text


def test_non_stream_chat():
    response = client.post("/api/chat", json=fast_payload(max_tokens=60))
    assert response.status_code == 200
    body = response.json()
    assert body["content"]
    assert body["finish_reason"] in {"stop", "length"}
    assert body["usage"]["completion_tokens"] > 0
    assert body["usage"]["total_tokens"] == body["usage"]["prompt_tokens"] + body["usage"]["completion_tokens"]
    assert response.headers["x-request-id"] == body["request_id"]


def test_non_stream_matches_stream_text():
    payload = fast_payload(max_tokens=40)
    expected = client.post("/api/chat", json=payload).json()

    with client.stream("POST", "/api/chat/stream", json=payload) as response:
        body = "".join(response.iter_text())
    events = parse_sse(body)
    streamed = "".join(item["data"]["delta"] for item in events if item["event"] == "token")

    assert streamed == expected["content"]
    assert events[-1]["data"]["finish_reason"] == expected["finish_reason"]


def test_sse_stream_event_order_and_headers():
    with client.stream("POST", "/api/chat/stream", json=fast_payload(max_tokens=30)) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-cache, no-transform"
        body = "".join(response.iter_text())

    events = parse_sse(body)
    names = [item["event"] for item in events]
    assert names[0] == "start"
    assert names[-2:] == ["usage", "done"]
    assert names.count("token") > 0

    start = events[0]["data"]
    assert response.headers["x-request-id"] == start["request_id"]
    assert start["model"] == "demo-1"

    usage = next(item["data"] for item in events if item["event"] == "usage")
    token_count = names.count("token")
    assert usage["usage"]["completion_tokens"] == token_count
    assert usage["usage"]["total_tokens"] == token_count + usage["usage"]["prompt_tokens"]
    assert usage["ttft_ms"] is not None
    assert usage["tokens_per_second"] > 0

    # token 事件的 id 应当严格递增
    token_ids = [item["id"] for item in events if item["event"] == "token"]
    assert token_ids == sorted(token_ids)
    assert len(set(token_ids)) == len(token_ids)


def test_sse_retry_field_is_first():
    with client.stream("POST", "/api/chat/stream", json=fast_payload()) as response:
        body = "".join(response.iter_text())
    assert body.startswith("retry: 3000\n\n")


def test_ndjson_stream():
    with client.stream("POST", "/api/chat/stream/ndjson", json=fast_payload(max_tokens=30)) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/x-ndjson")
        body = "".join(response.iter_text())

    lines = [line for line in body.splitlines() if line.strip()]
    assert len(lines) > 2
    parsed = [json.loads(line) for line in lines]
    assert parsed[0]["event"] == "start"
    assert parsed[-1]["event"] == "done"
    assert any(item["event"] == "token" for item in parsed)
    assert "".join(
        item["data"]["delta"] for item in parsed if item["event"] == "token"
    )


def test_max_tokens_truncation():
    with client.stream("POST", "/api/chat/stream", json=fast_payload(max_tokens=5)) as response:
        body = "".join(response.iter_text())
    events = parse_sse(body)
    tokens = [item for item in events if item["event"] == "token"]
    done = next(item["data"] for item in events if item["event"] == "done")
    assert len(tokens) == 5
    assert done["finish_reason"] == "length"


def test_stream_generation_error_is_in_band():
    with client.stream(
        "POST",
        "/api/chat/stream",
        json=fast_payload(prompt="请解释 __error__ 这个标记", max_tokens=10),
    ) as response:
        # 响应头已经发出，HTTP 状态仍然是 200
        assert response.status_code == 200
        body = "".join(response.iter_text())

    events = parse_sse(body)
    assert any(item["event"] == "error" for item in events)
    assert not any(item["event"] == "done" for item in events)
    error = next(item["data"] for item in events if item["event"] == "error")
    assert error["code"] == "generation_failed"


def test_non_stream_generation_error_returns_502():
    response = client.post(
        "/api/chat",
        json=fast_payload(prompt="请解释 __error__ 这个标记", max_tokens=10),
    )
    assert response.status_code == 502
    assert response.json()["code"] == "generation_failed"


@pytest.mark.parametrize(
    "payload",
    [
        {"prompt": "   "},
        {"prompt": "hi", "max_tokens": 0},
        {"prompt": "hi", "max_tokens": 9999},
        {"prompt": "x" * (settings.max_prompt_chars + 1)},
    ],
)
def test_invalid_payload_returns_422(payload):
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 422


def test_plain_text_echo_stream():
    with client.stream(
        "GET",
        "/api/stream/echo",
        params={"text": "hi", "repeat": 2, "interval_ms": 0},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        body = "".join(response.iter_text())
    assert body == "[1/2] hi\n[2/2] hi\n"


def test_cors_header():
    response = client.get("/api/health", headers={"Origin": "http://example.com"})
    assert response.headers["access-control-allow-origin"] == "*"


class _FakeRequest:
    """只实现 is_disconnected，用来在单元测试里模拟客户端断开。"""

    def __init__(self, disconnect_after: int):
        self.calls = 0
        self.disconnect_after = disconnect_after

    async def is_disconnected(self) -> bool:
        self.calls += 1
        return self.calls > self.disconnect_after


def test_client_disconnect_stops_generation():
    async def collect():
        payload = ChatRequest(
            prompt="测试断开",
            max_tokens=50,
            token_delay_ms=0,
            first_token_delay_ms=0,
        )
        events = []
        async for event in service.chat_events(payload, _FakeRequest(disconnect_after=1), "req_test"):
            events.append(event)
        return events

    events = asyncio.run(collect())
    names = [item[0] for item in events]
    assert names[0] == "start"
    assert names.count("token") == 1  # 发出一个 token 后发现断开，立即停止
    assert "done" not in names


def test_heartbeat_during_first_token_delay(monkeypatch):
    # 心跳间隔有 0.1s 的下限，测试里用 0.1s 间隔 + 0.25s 等待来观察 ping
    monkeypatch.setattr(settings, "heartbeat_interval_s", 0.1)

    async def collect():
        beats = 0
        async for _ in service._sleep_with_heartbeat(0.25, _FakeRequest(disconnect_after=999)):
            beats += 1
        return beats

    assert asyncio.run(collect()) >= 1
