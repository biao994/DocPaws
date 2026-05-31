"""
create_agent 编排：流式输出最终助手回复。
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Literal, TypedDict

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from docpaws.usecases.chat_agent_tools import AgentToolContext, build_agent_system_prompt, build_chat_agent_tools

logger = logging.getLogger(__name__)


class AgentStreamEvent(TypedDict):
    kind: Literal["tool_running", "answer_delta"]
    content: str


_TOOL_LABELS: dict[str, str] = {
    "count_scope_documents": "正在统计文档数量…",
    "list_scope_documents": "正在列出文档…",
    "lookup_scope_document": "正在查找文档…",
    "query_knowledge_base": "正在检索知识库…",
    "search_documents": "正在搜索文档片段…",
}


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


def _tool_call_name(tool_call) -> str:
    if isinstance(tool_call, dict):
        fn = tool_call.get("function") or tool_call.get("name")
        if isinstance(fn, dict):
            return str(fn.get("name") or "")
        return str(fn or tool_call.get("name") or "")
    fn = getattr(tool_call, "name", None) or getattr(tool_call, "function", None)
    if fn is not None and not isinstance(fn, str):
        return str(getattr(fn, "name", "") or "")
    return str(fn or "")


def _tool_running_label(tool_name: str) -> str:
    return _TOOL_LABELS.get(tool_name, f"正在执行 {tool_name}…")


def _extract_ai_from_state(state: dict) -> str:
    messages = state.get("messages") or []
    for msg in reversed(messages):
        if not _is_ai_message(msg):
            continue
        if getattr(msg, "tool_calls", None):
            continue
        text = _message_content(msg)
        if text:
            return text
    for msg in reversed(messages):
        if _is_ai_message(msg):
            text = _message_content(msg)
            if text:
                return text
    return ""


def _emit_tool_running_events(
    state_update: dict,
    *,
    announced: set[str],
) -> list[AgentStreamEvent]:
    events: list[AgentStreamEvent] = []
    for msg in state_update.get("messages") or []:
        for tc in getattr(msg, "tool_calls", None) or []:
            name = _tool_call_name(tc)
            if not name or name in announced:
                continue
            announced.add(name)
            events.append({"kind": "tool_running", "content": _tool_running_label(name)})
    return events


def _model_update_has_tool_calls(state_update: dict) -> bool:
    for msg in state_update.get("messages") or []:
        if getattr(msg, "tool_calls", None):
            return True
    return False


async def _stream_agent_plan_e(
    agent,
    inputs: dict,
    *,
    emit_tool_running: bool,
) -> AsyncGenerator[AgentStreamEvent, None]:
    """
    updates：工具调用前推 tool_running；工具跑完后才允许流最终答案。
    messages：只输出最终一轮 assistant content（跳过调工具轮碎片）。
    """
    answer_streaming_enabled = False
    announced_tools: set[str] = set()

    async for item in agent.astream(inputs, stream_mode=["messages", "updates"]):
        if not isinstance(item, tuple) or len(item) != 2:
            continue
        mode, data = item

        if mode == "updates":
            if not isinstance(data, dict):
                continue
            if "model" in data:
                model_update = data["model"]
                if isinstance(model_update, dict):
                    if emit_tool_running:
                        for ev in _emit_tool_running_events(model_update, announced=announced_tools):
                            yield ev
                    if not _model_update_has_tool_calls(model_update):
                        answer_streaming_enabled = True
            if "tools" in data:
                answer_streaming_enabled = True
            continue

        if mode != "messages" or not answer_streaming_enabled:
            continue

        if not isinstance(data, tuple) or len(data) != 2:
            continue
        msg, _meta = data
        if not _is_ai_message(msg):
            continue
        if getattr(msg, "tool_calls", None):
            continue

        # messages 模式下每个 chunk 是增量 token，不是累积全文
        delta = _message_content(msg)
        if delta:
            yield {"kind": "answer_delta", "content": delta}


async def run_agent_stream(
    *,
    llm,
    ctx: AgentToolContext,
    question: str,
    history_text: str,
    chat_mode: str = "fast",
) -> AsyncGenerator[AgentStreamEvent, None]:
    """
    运行 Agent：deep 模式可推 tool_running；answer_delta 流最终答案。
    失败时 fallback ainvoke，整段答案作为单个 answer_delta。
    """
    tools = build_chat_agent_tools(ctx)
    system_prompt = build_agent_system_prompt(ctx)
    agent = create_agent(model=llm, tools=tools, system_prompt=system_prompt)

    user_text = question.strip()
    if history_text:
        user_text = f"【历史对话】\n{history_text}\n\n【当前问题】\n{user_text}"

    inputs = {"messages": [HumanMessage(content=user_text)]}

    streamed_answer = False
    try:
        async for event in _stream_agent_plan_e(
            agent,
            inputs,
            emit_tool_running=(chat_mode == "deep"),
        ):
            if event.get("kind") == "answer_delta":
                streamed_answer = True
            yield event
    except Exception as e:
        logger.warning("agent astream(plan_e) failed, fallback to ainvoke: %s", e)

    if not streamed_answer:
        try:
            result = await agent.ainvoke(inputs)
            text = _extract_ai_from_state(result if isinstance(result, dict) else {})
            if text:
                yield {"kind": "answer_delta", "content": text}
        except Exception as e:
            logger.exception("agent ainvoke failed: %s", e)
            yield {"kind": "answer_delta", "content": "处理问题时出错，请稍后重试。"}
