"""
对话用 LLM 配置：DeepSeek V4-Flash + 快速/深度模式。
"""
from __future__ import annotations

import os
from typing import Any, Literal

from langchain_openai import ChatOpenAI

from docpaws.config import get_default_config

ChatMode = Literal["fast", "deep"]

DEFAULT_CHAT_MODEL = "deepseek-v4-flash"


def resolve_chat_model(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    cfg = get_default_config()
    return os.getenv("CHAT_MODEL") or cfg.get("model") or DEFAULT_CHAT_MODEL


def thinking_extra_body(chat_mode: ChatMode) -> dict[str, Any]:
    """Agent 主链路固定关闭 thinking（避免与 tool call 冲突）；深度思考由独立流式调用展示。"""
    if chat_mode == "deep":
        return {"thinking": {"type": "disabled"}}
    return {"thinking": {"type": "disabled"}}


def deep_thinking_extra_body() -> dict[str, Any]:
    return {"thinking": {"type": "enabled"}, "reasoning_effort": "high"}


def create_chat_llm(
    *,
    model_name: str | None = None,
    chat_mode: ChatMode = "fast",
    for_thinking_stream: bool = False,
    temperature: float | None = None,
) -> ChatOpenAI:
    cfg = get_default_config()
    model = resolve_chat_model(model_name)
    extra = deep_thinking_extra_body() if for_thinking_stream else thinking_extra_body(chat_mode)
    return ChatOpenAI(
        model=model,
        temperature=temperature if temperature is not None else cfg.get("temperature", 0.1),
        timeout=cfg.get("llm_timeout", 60 if for_thinking_stream else 30),
        max_retries=cfg.get("llm_max_retries", 3),
        api_key=cfg["llm_api_key"],
        base_url=cfg["llm_base_url"],
        extra_body=extra,
    )
