"""流式会话的核心：把「生成」和「传输协议」解耦。

``chat_events`` 只产出 ``(event, data, event_id)`` 三元组，
SSE 和 NDJSON 两个路由只负责把三元组编码成各自的协议帧。
这样新增一种协议（比如 WebSocket 或 gRPC stream）时不用重写业务逻辑。
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any, Literal, TypeAlias

from fastapi import Request

from . import llm
from .config import settings
from .models import ChatRequest, Usage

logger = logging.getLogger(__name__)

# (事件名, 事件数据, SSE 的 id；心跳等无 id 的事件传 None)
StreamEvent: TypeAlias = tuple[str, dict[str, Any], int | None]


class ClientDisconnected(Exception):
    """客户端主动断开连接，用于从生成器内部控制退出。"""


async def chat_events(
    payload: ChatRequest,
    request: Request,
    request_id: str,
) -> AsyncIterator[StreamEvent]:
    """一次流式对话的完整事件序列。

    正常顺序：start → (ping)* → (token)* → usage → done。
    生成中途失败时：start → (token)* → error（不会再发 done）。
    """
    created = int(time.time())
    started = time.perf_counter()
    first_token_at: float | None = None
    completion_tokens = 0
    finish_reason: Literal["stop", "length"] = "stop"
    event_id = 0
    outcome = "completed"

    logger.info(
        "stream start request_id=%s model=%s max_tokens=%d",
        request_id,
        payload.model,
        payload.max_tokens,
    )

    try:
        yield (
            "start",
            {
                "request_id": request_id,
                "model": payload.model,
                "created": created,
                "max_tokens": payload.max_tokens,
            },
            event_id,
        )
        event_id += 1

        # 首 token 之前可能等待较久（真实场景是 prefill / 排队）。
        # 按心跳周期切片 sleep，等待期间定时发 ping，避免网关把空闲连接掐掉。
        first_delay = payload.effective_first_token_delay_ms() / 1000
        async for _ in _sleep_with_heartbeat(first_delay, request):
            yield ("ping", {"request_id": request_id, "ts": _epoch_ms()}, None)

        token_delay = payload.effective_token_delay_ms() / 1000
        # 多取一个 token，用来区分「自然结束」和「被 max_tokens 截断」
        token_iter = llm.stream_tokens(payload.prompt, payload.max_tokens + 1)

        while True:
            if await request.is_disconnected():
                raise ClientDisconnected

            try:
                token = await token_iter.__anext__()
            except StopAsyncIteration:
                break

            if completion_tokens >= payload.max_tokens:
                finish_reason = "length"
                break

            now = time.perf_counter()
            if first_token_at is None:
                first_token_at = now  # 第一个 token 产出的瞬间，用于计算 TTFT

            yield ("token", {"index": completion_tokens, "delta": token}, event_id)
            event_id += 1
            completion_tokens += 1

            # 模拟逐 token 生成耗时；真实实现这里是 await 上游返回下一段
            if token_delay > 0:
                await asyncio.sleep(token_delay)
                if await request.is_disconnected():
                    raise ClientDisconnected

    except ClientDisconnected:
        outcome = "client_disconnected"
        logger.info(
            "stream disconnected request_id=%s tokens=%d",
            request_id,
            completion_tokens,
        )
    except asyncio.CancelledError:
        # ASGI 服务器取消任务时也会走这里；必须重新抛出，不能吞掉取消信号
        outcome = "cancelled"
        logger.info("stream cancelled request_id=%s tokens=%d", request_id, completion_tokens)
        raise
    except llm.GenerationError as exc:
        outcome = "generation_error"
        logger.warning("stream generation_error request_id=%s error=%s", request_id, exc)
        # 响应头早就发出去了，HTTP 状态码无法再改，只能在流内发一个 error 事件
        yield (
            "error",
            {
                "request_id": request_id,
                "code": "generation_failed",
                "message": str(exc),
            },
            None,
        )
    except Exception:
        outcome = "internal_error"
        logger.exception("stream internal_error request_id=%s", request_id)
        yield (
            "error",
            {
                "request_id": request_id,
                "code": "internal_error",
                "message": "生成过程中发生未知错误",
            },
            None,
        )
    else:
        # 只有正常走完（包括被 max_tokens 截断）才发送统计和结束事件
        elapsed_s = time.perf_counter() - started
        ttft_ms = (
            round((first_token_at - started) * 1000, 1) if first_token_at is not None else None
        )
        generation_s = max(time.perf_counter() - (first_token_at or started), 1e-9)
        prompt_tokens = llm.count_tokens(payload.prompt)
        usage = Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

        yield (
            "usage",
            {
                "request_id": request_id,
                "usage": usage.model_dump(),
                "ttft_ms": ttft_ms,
                "elapsed_ms": round(elapsed_s * 1000, 1),
                "tokens_per_second": round(completion_tokens / generation_s, 2)
                if completion_tokens
                else 0.0,
            },
            event_id,
        )
        event_id += 1
        yield (
            "done",
            {
                "request_id": request_id,
                "finish_reason": finish_reason,
                "created": created,
            },
            event_id,
        )
    finally:
        logger.info(
            "stream end request_id=%s outcome=%s tokens=%d finish_reason=%s",
            request_id,
            outcome,
            completion_tokens,
            finish_reason,
        )


async def _sleep_with_heartbeat(seconds: float, request: Request) -> AsyncIterator[None]:
    """分片等待；每到一个心跳周期就 yield 一次，让调用方插入 ping 事件。

    同时每个分片都检查客户端是否已断开，发现断开立即终止生成。
    """
    remaining = seconds
    interval = max(settings.heartbeat_interval_s, 0.1)
    while remaining > 0:
        step = min(remaining, interval)
        await asyncio.sleep(step)
        remaining -= step
        if await request.is_disconnected():
            raise ClientDisconnected
        if remaining > 0:
            yield None


def _epoch_ms() -> int:
    return int(time.time() * 1000)
