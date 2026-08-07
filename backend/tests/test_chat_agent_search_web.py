"""search_web Agent 工具：仅在配置 Key 时挂载，返回联网结果并写入 Web 引用。"""
from docpaws.settings import settings
from docpaws.usecases.chat_agent_tools import (
    AgentToolContext,
    build_chat_agent_tools,
)


def _ctx() -> AgentToolContext:
    return AgentToolContext(
        session=None,
        kb_id="kb1",
        scope_type="kb",
        scope_id=None,
        vectorstore=None,
        metadata_filter=None,
        search_k=5,
        cache_redis=None,
        artifact_id="art",
        scope_token="tok",
        model_name="m",
    )


def _find(tools, name):
    for t in tools:
        if getattr(t, "name", None) == name:
            return t
    return None


def test_search_web_absent_without_key(monkeypatch):
    monkeypatch.setattr(settings, "YDC_API_KEY", "")
    tools = build_chat_agent_tools(_ctx())
    assert _find(tools, "search_web") is None


def test_search_web_sets_web_citations(monkeypatch):
    monkeypatch.setattr(settings, "YDC_API_KEY", "k")
    fake = [
        {"title": "标题A", "url": "https://e.com/a", "snippet": "描述A"},
        {"title": "标题B", "url": "https://e.com/b", "snippet": "描述B"},
    ]
    monkeypatch.setattr(
        "docpaws.usecases.chat_agent_tools.youcom_web_search",
        lambda q, count=None: fake,
    )
    ctx = _ctx()
    tool = _find(build_chat_agent_tools(ctx), "search_web")
    assert tool is not None

    out = tool.invoke({"query": "最新进展"})
    assert "标题A" in out and "https://e.com/a" in out
    assert "来源: https://e.com/a" in out

    assert len(ctx.last_citations) == 2
    c0 = ctx.last_citations[0]
    assert c0["chunk_id"] == "web:0"
    assert c0["document_id"] == ""
    assert c0["source"] == "标题A"
    assert "https://e.com/a" in c0["snippet"]     # URL 随 snippet 保留，可持久化
    assert ctx.last_hit_chunks == []


def test_search_web_empty_query(monkeypatch):
    monkeypatch.setattr(settings, "YDC_API_KEY", "k")
    tool = _find(build_chat_agent_tools(_ctx()), "search_web")
    assert "不能为空" in tool.invoke({"query": "  "})
