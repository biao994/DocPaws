"""
create_agent 编排：流式输出最终助手回复。
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from docpaws.usecases.chat_agent_tools import AgentToolContext, build_agent_system_prompt, build_chat_agent_tools

logger = logging.getLogger(__name__)


def _message_content(msg) -> str:
    content = getattr(msg, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return ""


def _is_ai_message(msg) -> bool:
    if isinstance(msg, (AIMessage, AIMessageChunk)):
        return True
    role = getattr(msg, "type", None)
    return role in ("ai", "AIMessageChunk")


def _extract_ai_from_state(state: dict) -> str:
    messages = state.get("messages") or []
    for msg in reversed(messages):
        if _is_ai_message(msg):
            text = _message_content(msg)
            if text:
                return text
    return ""


async def run_agent_stream(
    *,
    llm,
    ctx: AgentToolContext,
    question: str,
    history_text: str,
) -> AsyncGenerator[str, None]:
    """
    运行 Agent 并流式产出最终回复文本（工具内部 LLM 不流式）。
    """
    tools = build_chat_agent_tools(ctx)
    system_prompt = build_agent_system_prompt(ctx)
    agent = create_agent(model=llm, tools=tools, system_prompt=system_prompt)

    user_text = question.strip()
    if history_text:
        user_text = f"【历史对话】\n{history_text}\n\n【当前问题】\n{user_text}"

    inputs = {"messages": [HumanMessage(content=user_text)]}

    streamed_any = False
    last_sent_len = 0
    try:
        async for item in agent.astream(inputs, stream_mode="messages"):
            msg = item[0] if isinstance(item, tuple) and item else item
            if not _is_ai_message(msg):
                continue
            full = _message_content(msg)
            if len(full) <= last_sent_len:
                continue
            delta = full[last_sent_len:]
            last_sent_len = len(full)
            streamed_any = True
            yield delta
    except Exception as e:
        logger.warning("agent astream(messages) failed, fallback to ainvoke: %s", e)

    if not streamed_any:
        try:
            result = await agent.ainvoke(inputs)
            text = _extract_ai_from_state(result if isinstance(result, dict) else {})
            if text:
                yield text
        except Exception as e:
            logger.exception("agent ainvoke failed: %s", e)
            yield "处理问题时出错，请稍后重试。"
