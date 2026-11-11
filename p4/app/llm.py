"""一个确定性的「假模型」。

它不调用任何外部服务，只负责把一段固定文案切成 token 后逐个吐出，
这样可以把注意力放在 FastAPI 的流式传输上；替换成真实 LLM 时，
只需让 ``stream_tokens`` 变成对上游 SDK 的异步迭代即可。
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Literal

# 英文按单词、CJK 按单字、标点和空白各自成一个 token。
# 真实 LLM 使用 BPE/WordPiece，这里刻意切得碎一点，让流式过程肉眼可见。
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?|\s+|[^\sA-Za-z0-9]")


class GenerationError(RuntimeError):
    """模拟推理中途失败：真实场景可能是上游超时、限流或内容审核拦截。"""


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def count_tokens(text: str) -> int:
    return len(tokenize(text))


def build_answer(prompt: str) -> str:
    """按关键词返回不同文案，顺便避免把用户输入原样拼得太长。"""
    shown = prompt if len(prompt) <= 60 else prompt[:60] + "…"
    lowered = prompt.lower()

    if "流式" in prompt or "stream" in lowered or "sse" in lowered:
        return (
            f"关于「{shown}」，这是一个用 FastAPI 实现的流式接口演示。\n\n"
            "这段文字不是一次性返回的：服务端每生成一小段内容，就立刻通过 HTTP 分块传输推给客户端，"
            "所以你能看到文字逐个出现。\n\n"
            "实现流式响应的关键点：\n"
            "1. 用 async generator 逐段产出数据，而不是先拼出完整结果；\n"
            "2. 用 StreamingResponse 包装生成器，并声明正确的 Content-Type；\n"
            "3. SSE 必须遵守 event、data、id 和空行的帧格式，同时关闭代理缓冲；\n"
            "4. 客户端断开后及时停止生成，避免浪费算力和上游调用。\n\n"
            "试着修改 max_tokens 或 token 间隔，观察首字延迟 TTFT 和吞吐的变化。"
        )

    return (
        f"你问的是「{shown}」。\n\n"
        "这是一个流式 API 演示，回答由本地假模型逐 token 生成，不会调用任何外部服务。"
        "服务端使用 FastAPI 的 StreamingResponse 配合异步生成器，"
        "通过 SSE 或 NDJSON 协议把内容持续推送给客户端。\n\n"
        "可以把 prompt 换成包含「流式」或「stream」的问题，看看另一个回答模板。"
    )


async def stream_tokens(prompt: str, limit: int) -> AsyncIterator[str]:
    """逐个产出 token，最多 ``limit`` 个。

    这里没有 ``await asyncio.sleep``：生成节奏由传输层控制，
    这样同一份生成逻辑既能用于流式接口，也能用于非流式接口。
    """
    tokens = tokenize(build_answer(prompt))
    for index, token in enumerate(tokens):
        if index >= limit:
            return
        # 固定在第 4 个 token 处失败，方便稳定复现「流到一半出错」的场景
        if index == 3 and "__error__" in prompt:
            raise GenerationError("模拟上游模型在生成过程中失败")
        yield token


async def collect_answer(prompt: str, max_tokens: int) -> tuple[str, Literal["stop", "length"]]:
    """非流式聚合：返回 (完整文本, finish_reason)。

    多取一个 token 用来判断是自然结束还是被 max_tokens 截断。
    """
    parts: list[str] = []
    finish_reason: Literal["stop", "length"] = "stop"
    index = 0
    async for token in stream_tokens(prompt, max_tokens + 1):
        if index >= max_tokens:
            finish_reason = "length"
            break
        parts.append(token)
        index += 1
    return "".join(parts), finish_reason
