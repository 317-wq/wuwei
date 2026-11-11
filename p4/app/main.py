"""FastAPI 流式接口演示。

启动方式::

    uvicorn app.main:app --reload --port 8000
    python -m app.main            # 等价，方便 IDE 直接运行

三种流式形态：
- POST /api/chat/stream         SSE（text/event-stream）
- POST /api/chat/stream/ndjson  NDJSON（application/x-ndjson）
- GET  /api/stream/echo         最朴素的纯文本分块传输

另外提供 POST /api/chat 作为非流式对照组。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import llm
from .config import settings
from .models import ChatRequest, ChatResponse, Usage
from .service import chat_events
from .sse import ndjson_event, sse_event, sse_retry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("%s v%s 已启动，演示页 http://127.0.0.1:8000/", settings.app_name, settings.version)
    yield
    logger.info("服务已关闭")


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "一个不依赖外部模型服务的流式 API 演示：异步生成器逐 token 产出内容，"
        "通过 SSE / NDJSON / 纯文本三种方式推送给客户端。"
    ),
    lifespan=lifespan,
)

# 演示页和接口同源，这里放开 CORS 主要是方便用其他前端项目联调
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """浏览器可视化演示页。"""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)  # 避免浏览器请求 404 刷日志


@app.get("/api/health", tags=["meta"], summary="健康检查")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.version,
        "timestamp": int(time.time()),
    }


@app.post("/api/chat", response_model=ChatResponse, tags=["chat"], summary="非流式对话（对照组）")
async def chat(payload: ChatRequest, response: Response) -> ChatResponse:
    """一次性返回完整答案，方便与流式接口对比首字延迟和总耗时。"""
    request_id = _new_request_id()
    response.headers["X-Request-ID"] = request_id
    started = time.perf_counter()

    # 这里不模拟逐 token 的耗时，否则「非流式」反而要等完整生成
    content, finish_reason = await llm.collect_answer(payload.prompt, payload.max_tokens)
    prompt_tokens = llm.count_tokens(payload.prompt)
    completion_tokens = llm.count_tokens(content)
    usage = Usage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )
    return ChatResponse(
        request_id=request_id,
        model=payload.model,
        content=content,
        finish_reason=finish_reason,
        usage=usage,
        created=int(time.time()),
        elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
    )


@app.post(
    "/api/chat/stream",
    tags=["streaming"],
    summary="流式对话（SSE）",
    responses={
        200: {
            "description": "SSE 事件流：start / ping / token / usage / done / error",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
async def chat_stream_sse(payload: ChatRequest, request: Request) -> StreamingResponse:
    """浏览器端可用 ``fetch`` + ``ReadableStream`` 消费；由于是 POST，不能用 EventSource。"""
    request_id = _new_request_id()

    async def event_stream():
        # SSE 建议在流开头声明重连间隔（毫秒）
        yield sse_retry(settings.sse_retry_ms)
        async for event, data, event_id in chat_events(payload, request, request_id):
            yield sse_event(event, data, event_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            # 关闭缓存和代理缓冲，否则 Nginx 可能攒满一个 buffer 才下发
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Request-ID": request_id,
        },
    )


@app.post(
    "/api/chat/stream/ndjson",
    tags=["streaming"],
    summary="流式对话（NDJSON）",
    responses={
        200: {
            "description": "每行一个 JSON：{\"event\": \"token\", \"data\": {...}}",
            "content": {"application/x-ndjson": {"schema": {"type": "string"}}},
        }
    },
)
async def chat_stream_ndjson(payload: ChatRequest, request: Request) -> StreamingResponse:
    """NDJSON 比 SSE 更简单：一行一个 JSON，客户端按换行切分即可。"""
    request_id = _new_request_id()

    async def event_stream():
        async for event, data, _event_id in chat_events(payload, request, request_id):
            yield ndjson_event(event, data)

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Request-ID": request_id,
        },
    )


@app.get(
    "/api/stream/echo",
    tags=["streaming"],
    summary="纯文本分块输出（最简单的流式响应）",
)
async def stream_echo(
    request: Request,
    text: str = Query(default="Hello, streaming world!", max_length=200, description="要重复输出的文本"),
    repeat: int = Query(default=3, ge=1, le=20, description="重复行数"),
    interval_ms: int = Query(default=120, ge=0, le=1000, description="每个字符之间的间隔（毫秒）"),
) -> StreamingResponse:
    """用 ``curl -N`` 可以直接看到字符逐个出现，适合验证分块传输本身。"""

    async def generate():
        for line_no in range(1, repeat + 1):
            line = f"[{line_no}/{repeat}] {text}\n"
            for char in line:
                if await request.is_disconnected():
                    logger.info("echo stream disconnected at line=%d", line_no)
                    return
                if interval_ms > 0:
                    await asyncio.sleep(interval_ms / 1000)
                yield char

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Request-ID": _new_request_id(),
        },
    )


@app.exception_handler(llm.GenerationError)
async def generation_error_handler(_request: Request, exc: llm.GenerationError) -> JSONResponse:
    """非流式接口可以正常返回 502；流式接口的同类错误只能通过 error 事件传递。"""
    return JSONResponse(
        status_code=502,
        content={"code": "generation_failed", "message": str(exc)},
    )


def _new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
