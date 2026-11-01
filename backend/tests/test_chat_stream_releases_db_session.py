"""SSE 推流期间不得长时间占用 DB Session（连接短借短还）。"""
from __future__ import annotations

import json
from contextlib import contextmanager

import docpaws.infra.db.session as db_session_mod
import docpaws.usecases.chat_agent_runner as agent_runner
import docpaws.usecases.chat_service as chat_service
from docpaws.domain.models.document import Chunk, Document
from docpaws.domain.models.index import IndexArtifact


class _FakeDoc:
    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata


def test_chat_stream_holds_no_session_scope_during_agent(
    auth_client, db_session, monkeypatch, tmp_path
):
    """Agent 吐字时 session_scope 应已退出（嵌套深度 0）。"""
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb-pool", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    doc = Document(kb_id=kb_id, title="t1", content="c")
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    db_session.add(Chunk(document_id=doc.id, content="文档内容"))
    db_session.commit()
    db_session.add(
        IndexArtifact(
            kb_id=kb_id,
            version=1,
            index_path=str(tmp_path / "fake_index"),
            index_job_id="job1",
            is_active=True,
        )
    )
    db_session.commit()

    def _fake_build_retriever(index_path: str):
        class _VS:
            def similarity_search(self, question, k=5, filter=None, fetch_k=20, **kwargs):
                return [
                    _FakeDoc(
                        page_content="文档内容",
                        metadata={"chunk_id": "", "document_id": "", "source": "doc1"},
                    )
                ]

            def similarity_search_with_score(
                self, question, k=5, filter=None, fetch_k=20, **kwargs
            ):
                doc = _FakeDoc(
                    page_content="文档内容",
                    metadata={"chunk_id": "", "document_id": "", "source": "doc1"},
                )
                return [(doc, 0.05)]

        return None, _VS()

    depth = {"n": 0}
    depths_during_agent: list[int] = []
    real_scope = db_session_mod.session_scope

    @contextmanager
    def tracking_scope():
        depth["n"] += 1
        try:
            with real_scope() as session:
                yield session
        finally:
            depth["n"] -= 1

    async def _fake_run_agent_stream(**kwargs):
        depths_during_agent.append(depth["n"])
        yield {"kind": "answer_delta", "content": "你好"}

    monkeypatch.setattr(chat_service, "build_retriever", _fake_build_retriever)
    monkeypatch.setattr(agent_runner, "run_agent_stream", _fake_run_agent_stream)
    # 业务侧经 docpaws.infra.db.session.session_scope 取用，统一打点嵌套深度
    monkeypatch.setattr(db_session_mod, "session_scope", tracking_scope)

    with auth_client.stream(
        "POST",
        "/api/v1/chat/stream",
        json={"kb_id": kb_id, "question": "hi", "conversation_id": None},
    ) as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if not line:
                continue
            payload = json.loads(line[len("data: ") :])
            if payload.get("finished"):
                break

    assert depths_during_agent, "agent stream should have run"
    assert all(d == 0 for d in depths_during_agent), (
        f"DB session_scope still open during agent stream: {depths_during_agent}"
    )
