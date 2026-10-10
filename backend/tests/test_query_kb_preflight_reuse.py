"""query_knowledge_base：复用预检片段，不二次检索、不嵌套 LLM。"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from langchain_core.documents import Document as LCDocument

from docpaws.usecases.chat_agent_tools import AgentToolContext, build_chat_agent_tools
from docpaws.usecases.chat_scope import SCOPE_KB
from docpaws.usecases.chat_service import normalize_question


def _pinned_docs():
    return [
        LCDocument(
            page_content="星河科技成立于 2018 年。",
            metadata={
                "chunk_id": "c1",
                "document_id": "d1",
                "source": "公司简介.pdf",
            },
        )
    ]


def _make_ctx(db_session, *, question: str, docs: list):
    return AgentToolContext(
        session=db_session,
        kb_id="kb-preflight",
        scope_type=SCOPE_KB,
        scope_id=None,
        vectorstore=MagicMock(),
        metadata_filter=None,
        search_k=5,
        cache_redis=None,
        artifact_id="art-1",
        scope_token="kb:",
        model_name="dummy",
        preflight_question=normalize_question(question),
        preflight_docs=docs,
    )


def _tool_by_name(tools, name: str):
    for t in tools:
        if getattr(t, "name", None) == name:
            return t
    raise AssertionError(f"tool not found: {name}")


def test_query_kb_reuses_preflight_docs_without_retrieve_or_nested_llm(
    db_session, monkeypatch
):
    """同一问法：不调检索、不调工具内 LLM，返回片段正文。"""
    question = "星河科技哪年成立？"
    docs = _pinned_docs()
    ctx = _make_ctx(db_session, question=question, docs=docs)
    tools = build_chat_agent_tools(ctx)
    query = _tool_by_name(tools, "query_knowledge_base")

    retrieve_calls = {"n": 0}
    llm_calls = {"n": 0}

    def _fake_retrieve(**kwargs):
        retrieve_calls["n"] += 1
        return docs

    def _fake_create_llm(**kwargs):
        llm_calls["n"] += 1
        raise AssertionError("query_knowledge_base must not create nested LLM")

    import docpaws.usecases.chat_service as chat_service
    import docpaws.usecases.chat_llm as chat_llm

    monkeypatch.setattr(chat_service, "retrieve_scoped_docs_cached", _fake_retrieve)
    monkeypatch.setattr(chat_llm, "create_chat_llm", _fake_create_llm)

    out = asyncio.run(query.ainvoke({"question": question}))

    assert retrieve_calls["n"] == 0
    assert llm_calls["n"] == 0
    assert "星河科技成立于 2018 年" in out
    assert "公司简介.pdf" in out
    assert ctx.last_citations, "复用预检片段仍应合并引用"


def test_query_kb_retrieves_when_question_differs_from_preflight(
    db_session, monkeypatch
):
    """问法变了：仍走检索，仍不嵌套 LLM。"""
    preflight_q = "星河科技哪年成立？"
    other_q = "星河科技主营业务是什么？"
    docs = _pinned_docs()
    other_docs = [
        LCDocument(
            page_content="主营云计算与企业软件。",
            metadata={
                "chunk_id": "c2",
                "document_id": "d1",
                "source": "公司简介.pdf",
            },
        )
    ]
    ctx = _make_ctx(db_session, question=preflight_q, docs=docs)
    tools = build_chat_agent_tools(ctx)
    query = _tool_by_name(tools, "query_knowledge_base")

    retrieve_calls = {"n": 0}
    llm_calls = {"n": 0}

    def _fake_retrieve(**kwargs):
        retrieve_calls["n"] += 1
        return other_docs

    def _fake_create_llm(**kwargs):
        llm_calls["n"] += 1
        raise AssertionError("query_knowledge_base must not create nested LLM")

    import docpaws.usecases.chat_service as chat_service
    import docpaws.usecases.chat_llm as chat_llm

    monkeypatch.setattr(chat_service, "retrieve_scoped_docs_cached", _fake_retrieve)
    monkeypatch.setattr(chat_llm, "create_chat_llm", _fake_create_llm)

    out = asyncio.run(query.ainvoke({"question": other_q}))

    assert retrieve_calls["n"] == 1
    assert llm_calls["n"] == 0
    assert "主营云计算" in out
