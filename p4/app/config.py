"""应用配置。

演示用的节奏参数全部支持环境变量覆盖，方便在面试现场调整：
例如 ``DEMO_TOKEN_DELAY_MS=100 uvicorn app.main:app`` 可以让输出更慢、更直观。
"""

from __future__ import annotations

import os


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:  # 环境变量写错时退回默认值，不让服务起不来
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


class Settings:
    """一组不可变的运行时参数（这里用类属性，读取成本最低）。"""

    app_name = "FastAPI Streaming Demo"
    version = "1.0.0"

    # ---- 模拟模型的生成节奏 ----
    first_token_delay_ms = _int_env("DEMO_FIRST_TOKEN_DELAY_MS", 500)
    token_delay_ms = _int_env("DEMO_TOKEN_DELAY_MS", 20)

    # ---- 连接保活与协议参数 ----
    heartbeat_interval_s = _float_env("DEMO_HEARTBEAT_INTERVAL_S", 5.0)
    sse_retry_ms = _int_env("DEMO_SSE_RETRY_MS", 3000)

    # ---- 请求校验上限，防止演示接口被拿来跑长任务 ----
    max_prompt_chars = _int_env("DEMO_MAX_PROMPT_CHARS", 2000)
    max_tokens_limit = _int_env("DEMO_MAX_TOKENS_LIMIT", 512)
    max_token_delay_ms = _int_env("DEMO_MAX_TOKEN_DELAY_MS", 300)
    max_first_token_delay_ms = _int_env("DEMO_MAX_FIRST_TOKEN_DELAY_MS", 10_000)


settings = Settings()
