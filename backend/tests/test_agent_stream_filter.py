"""Agent 流式：忽略工具内嵌套 LLM 的 token，避免并行 query 拉链乱码。"""
from __future__ import annotations

import pytest

from docpaws.usecases.chat_agent_runner import _should_stream_answer_message


@pytest.mark.parametrize(
    "meta,tool_calls,expect",
    [
        ({"langgraph_node": "model", "langgraph_checkpoint_ns": ""}, None, True),
        ({"langgraph_node": "model", "checkpoint_ns": "agent"}, None, True),
        (
            {
                "langgraph_node": "model",
                "langgraph_checkpoint_ns": "tools:query_knowledge_base:abc",
            },
            None,
            False,
        ),
        (
            {
                "langgraph_node": "model",
                "checkpoint_ns": "run|tools:foo",
            },
            None,
            False,
        ),
        ({"langgraph_node": "model", "langgraph_checkpoint_ns": ""}, [{"name": "x"}], False),
    ],
)
def test_should_stream_answer_message(meta, tool_calls, expect):
    class Msg:
        type = "ai"

        def __init__(self):
            self.tool_calls = tool_calls
            self.content = "hi"

    assert _should_stream_answer_message(Msg(), meta) is expect
