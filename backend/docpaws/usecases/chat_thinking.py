"""
深度模式：独立流式输出思考过程（reasoning_content），不与 Agent 工具调用混用。

使用 OpenAI 兼容客户端直连，避免 LangChain 流式丢失 reasoning_content。
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI

from docpaws.config import get_default_config
from docpaws.usecases.chat_llm import deep_thinking_extra_body, resolve_chat_model

logger = logging.getLogger(__name__)

_THINKING_SYSTEM = """你是 DocPaws 知识库助手的「思考过程」展示模块。你的输出会原样展示给用户，用于说明你将如何回答。

要求：
1. 只写思考与分析，不要写最终答案、不要写完整总结段落、不要假装已经检索过文档。
2. 用中文，分步骤展开（建议 4～8 步），每步 1～3 句话，总篇幅建议 200～600 字。
3. 必须覆盖：用户意图、当前范围含义、是否需要统计/列文档/向量问答/关键词搜索、信息是否可能不足、回答结构计划。
4. 语气像人在认真推敲，避免「分析的内容」这类空泛一句带过。

可用工具（由后续 Agent 执行，你只做规划）：
- count_scope_documents：统计范围内文档数量
- list_scope_documents：列出文档标题
- query_knowledge_base：向量检索并基于片段生成回答（适合总结、解释、对比）
- search_documents：关键词检索（适合找包含特定词的文件）"""


def _build_user_message(
    *,
    question: str,
    history_text: str,
    scope_label: str,
    doc_count: int | None,
) -> str:
    parts: list[str] = []
    if history_text:
        parts.append(f"近期对话：\n{history_text}")
    parts.append(f"当前范围：{scope_label}")
    if doc_count is not None:
        parts.append(f"范围内约 {doc_count} 篇已索引文档")
    parts.append(f"用户问题：{question.strip()}")
    parts.append("请输出详细的思考过程（不要输出最终答案）。")
    return "\n\n".join(parts)


def _extract_delta_reasoning(delta) -> str:
    rc = getattr(delta, "reasoning_content", None)
    if isinstance(rc, str) and rc:
        return rc
    return ""


def _extract_delta_content(delta) -> str:
    c = getattr(delta, "content", None)
    if isinstance(c, str) and c:
        return c
    return ""


async def stream_thinking_prelude(
    *,
    model_name: str,
    question: str,
    history_text: str,
    scope_label: str,
    doc_count: int | None = None,
) -> AsyncGenerator[str, None]:
    """
    深度模式前置思考流。优先输出 reasoning_content 增量；无 reasoning 时用 content 兜底。
    """
    cfg = get_default_config()
    api_key = cfg.get("llm_api_key")
    base_url = cfg.get("llm_base_url")
    if not api_key:
        yield "未配置 LLM API Key，将直接检索知识库回答。\n"
        return

    model = resolve_chat_model(model_name)
    client = AsyncOpenAI(api_key=api_key, base_url=base_url, max_retries=cfg.get("llm_max_retries", 3))
    extra_body = deep_thinking_extra_body()
    user_msg = _build_user_message(
        question=question,
        history_text=history_text,
        scope_label=scope_label,
        doc_count=doc_count,
    )

    messages = [
        {"role": "system", "content": _THINKING_SYSTEM},
        {"role": "user", "content": user_msg},
    ]

    reasoning_total = 0
    content_total = 0

    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            temperature=0.3,
            max_tokens=int(cfg.get("thinking_max_tokens", 2048)),
            extra_body=extra_body,
            timeout=float(cfg.get("thinking_timeout", 90)),
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            rc = _extract_delta_reasoning(delta)
            if rc:
                reasoning_total += len(rc)
                yield rc
                continue
            # 部分模型/网关不把思考放进 reasoning_content，仅在 content 里流式输出
            cc = _extract_delta_content(delta)
            if cc and reasoning_total == 0:
                content_total += len(cc)
                yield cc
    except Exception as e:
        logger.warning("thinking stream failed: %s", e)
        yield (
            "【思考过程】\n"
            "1. 理解问题：需要结合当前知识库范围作答。\n"
            "2. 计划：先通过向量检索获取相关文档片段，再组织成通俗易懂的回答。\n"
            "3. 注意：若检索结果不足，会说明信息有限。\n"
        )
        return

    if reasoning_total + content_total < 40:
        yield (
            "\n\n（补充）将使用 query_knowledge_base 检索与问题相关的文档片段，"
            "再按用户要求组织成结构化回答；若需了解库内规模会先统计或列出文档。\n"
        )
