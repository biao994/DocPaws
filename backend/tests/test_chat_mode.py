import json


def test_chat_stream_deep_emits_thinking_chunk(auth_client, db_session, monkeypatch, tmp_path):
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb-deep", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    from docpaws.domain.models.document import Document, Chunk
    from docpaws.domain.models.index import IndexArtifact

    doc = Document(kb_id=kb_id, title="t1", content="c")
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    db_session.add(Chunk(document_id=doc.id, content="文档内容"))
    db_session.commit()

    artifact = IndexArtifact(
        kb_id=kb_id,
        version=1,
        index_path=str(tmp_path / "fake_index"),
        index_job_id="job1",
        is_active=True,
    )
    db_session.add(artifact)
    db_session.commit()

    import docpaws.usecases.chat_service as chat_service
    import docpaws.usecases.chat_agent_runner as agent_runner

    def _fake_build_retriever(index_path: str):
        class _VS:
            def similarity_search(self, question, k=5, filter=None, fetch_k=20, **kwargs):
                return []

            def similarity_search_with_score(self, question, k=5, filter=None, fetch_k=20, **kwargs):
                return []

        return None, _VS()

    async def _fake_thinking(**kwargs):
        yield "1. 理解用户希望用大白话总结知识库主题。\n"
        yield "2. 计划使用 query_knowledge_base 检索多个文档片段后归纳。\n"
        yield "3. 注意范围是整个知识库，需覆盖主要文档类型。\n"

    async def _fake_run_agent_stream(**kwargs):
        yield {"kind": "answer_delta", "content": "最终回答"}

    monkeypatch.setattr(chat_service, "build_retriever", _fake_build_retriever)
    monkeypatch.setattr(chat_service, "stream_thinking_prelude", _fake_thinking)
    monkeypatch.setattr(agent_runner, "run_agent_stream", _fake_run_agent_stream)

    events: list[str] = []
    thinking_parts: list[str] = []
    with auth_client.stream(
        "POST",
        "/api/v1/chat/stream",
        json={"kb_id": kb_id, "question": "hi", "conversation_id": None, "chat_mode": "deep"},
    ) as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            payload = json.loads(line[5:].strip())
            ev = payload.get("event") or payload.get("type")
            if ev:
                events.append(ev)
            if ev == "thinking_chunk":
                thinking_parts.append(payload.get("content", ""))

    assert "thinking_chunk" in events
    joined = "".join(thinking_parts)
    assert "理解用户" in joined
    assert "query_knowledge_base" in joined
    assert "answer_chunk" in events
