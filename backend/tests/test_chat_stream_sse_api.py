import json


class _FakeDoc:
    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata


class _FakeChunk:
    def __init__(self, content: str):
        self.content = content


def test_chat_stream_sse_returns_ids(auth_client, db_session, monkeypatch, tmp_path):
    # 1) create KB
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb1", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    # 2) 满足 ensure_kb_and_index_ready：至少一条 Document + Chunk
    from docpaws.domain.models.document import Document, Chunk
    from docpaws.domain.models.index import IndexArtifact

    doc = Document(kb_id=kb_id, title="t1", content="c")
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    db_session.add(Chunk(document_id=doc.id, content="文档内容"))
    db_session.commit()

    # 3) dummy active IndexArtifact（索引路径由 monkeypatch 接管）
    artifact = IndexArtifact(
        kb_id=kb_id,
        version=1,
        index_path=str(tmp_path / "fake_index"),
        index_job_id="job1",
        is_active=True,
    )
    db_session.add(artifact)
    db_session.commit()

    # 4) monkeypatch retriever + LLM so we don't touch FAISS/OpenAI
    import docpaws.usecases.chat_service as chat_service

    def _fake_build_retriever(index_path: str):
        class _VS:
            def similarity_search(self, question, k=5, filter=None, fetch_k=20, **kwargs):
                return [
                    _FakeDoc(
                        page_content="文档内容",
                        metadata={"chunk_id": "", "document_id": "", "source": "doc1"},
                    )
                ]

            def similarity_search_with_score(self, question, k=5, filter=None, fetch_k=20, **kwargs):
                doc = _FakeDoc(
                    page_content="文档内容",
                    metadata={"chunk_id": "", "document_id": "", "source": "doc1"},
                )
                return [(doc, 0.05)]

        return None, _VS()

    async def _fake_run_agent_stream(**kwargs):
        yield "你好"

    import docpaws.usecases.chat_agent_runner as agent_runner

    monkeypatch.setattr(chat_service, "build_retriever", _fake_build_retriever)
    monkeypatch.setattr(agent_runner, "run_agent_stream", _fake_run_agent_stream)

    # 5) call SSE endpoint
    with auth_client.stream(
        "POST",
        "/api/v1/chat/stream",
        json={"kb_id": kb_id, "question": "hi", "conversation_id": None},
    ) as resp:
        assert resp.status_code == 200

        last_payload = None
        for line in resp.iter_lines():
            if not line:
                continue
            assert line.startswith("data: ")
            payload = json.loads(line[len("data: ") :])
            last_payload = payload
            if payload.get("finished"):
                break

    assert last_payload is not None
    assert last_payload.get("finished") is True
    assert last_payload.get("conversation_id"), "SSE finished payload must include conversation_id"
    assert last_payload.get("message_id"), "SSE finished payload must include message_id"
    assert last_payload.get("answer_id"), "SSE finished payload must include answer_id"

