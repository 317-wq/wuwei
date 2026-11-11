"""请求 / 响应的数据模型（Pydantic v2）。

FastAPI 会自动用这些模型做参数校验并生成 OpenAPI 文档，
非法参数会在进入业务逻辑前直接返回 422。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .config import settings


class ChatRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=settings.max_prompt_chars,
        description="用户问题，不能为空白字符",
        examples=["用三句话解释 FastAPI 的流式响应是怎么实现的"],
    )
    model: str = Field(default="demo-1", min_length=1, max_length=64, description="模型名（演示用）")
    max_tokens: int = Field(default=300, ge=1, le=settings.max_tokens_limit, description="最多生成多少个 token")
    token_delay_ms: int | None = Field(
        default=None,
        ge=0,
        le=settings.max_token_delay_ms,
        description="覆盖默认的 token 间隔（毫秒），传 0 可全速返回",
    )
    first_token_delay_ms: int | None = Field(
        default=None,
        ge=0,
        le=settings.max_first_token_delay_ms,
        description="覆盖首 token 之前的等待时间（毫秒），用于模拟 prefill / 排队",
    )

    @field_validator("prompt")
    @classmethod
    def _prompt_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("prompt 不能是空白字符")
        return value

    def effective_token_delay_ms(self) -> int:
        return settings.token_delay_ms if self.token_delay_ms is None else self.token_delay_ms

    def effective_first_token_delay_ms(self) -> int:
        return (
            settings.first_token_delay_ms
            if self.first_token_delay_ms is None
            else self.first_token_delay_ms
        )


class Usage(BaseModel):
    """与 OpenAI 风格的 usage 字段保持一致，方便客户端复用解析逻辑。"""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatResponse(BaseModel):
    """非流式接口的响应体，用来和流式接口做对照。"""

    request_id: str
    model: str
    content: str
    finish_reason: Literal["stop", "length"]
    usage: Usage
    created: int
    elapsed_ms: float
