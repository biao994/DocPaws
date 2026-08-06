"""问答按用户限流：第一刀 —— 开启后超次数 → 429，且不碰模型。"""


class _FakeDoc:
    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata


class _FakeRedis:
    """假 Redis：支持限流用到的 incr / expire（以及检索缓存 get/set）。"""

    def __init__(self):
        self._kv: dict[str, int | bytes] = {}
        self._ttl: dict[str, int] = {}

    def incr(self, key: str) -> int:
        cur = self._kv.get(key, 0)
        if isinstance(cur, bytes):
            cur = int(cur)
        nxt = int(cur) + 1
        self._kv[key] = nxt
        return nxt

    def expire(self, key: str, seconds: int) -> bool:
        self._ttl[key] = seconds
        return True

    def get(self, key: str):
        return self._kv.get(key)

    def set(self, key: str, value, ex: int | None = None, nx: bool | None = None):
        if nx and key in self._kv:
            return False
        self._kv[key] = value
        if ex is not None:
            self._ttl[key] = ex
        return True


def _seed_ready_kb(auth_client, db_session, tmp_path) -> str:
    r = auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "kb-rl", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    from docpaws.domain.models.document import Chunk, Document
    from docpaws.domain.models.index import IndexArtifact

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
            index_job_id="job-rl",
            is_active=True,
        )
    )
    db_session.commit()
    return kb_id


def test_chat_rate_limit_exceeded_returns_429_without_calling_llm(
    auth_client, db_session, monkeypatch, tmp_path
):
    """开启限流 + 假 Redis：同一用户超过每分钟次数 → 429 RATE_LIMITED，且不调模型。"""
    from docpaws.settings import settings

    kb_id = _seed_ready_kb(auth_client, db_session, tmp_path)

    fake_redis = _FakeRedis()
    agent_calls = {"n": 0}
    retrieve_calls = {"n": 0}

    import docpaws.usecases.chat_service as chat_service
    import docpaws.usecases.chat_agent_runner as agent_runner
    import docpaws.infra.cache.redis_client as redis_client

    def _fake_build_retriever(index_path: str):
        class _VS:
            def similarity_search(self, question, k=5, filter=None, fetch_k=20, **kwargs):
                retrieve_calls["n"] += 1
                return [
                    _FakeDoc(
                        page_content="文档内容",
                        metadata={"chunk_id": "", "document_id": "", "source": "doc1"},
                    )
                ]

            def similarity_search_with_score(self, question, k=5, filter=None, fetch_k=20, **kwargs):
                retrieve_calls["n"] += 1
                doc = _FakeDoc(
                    page_content="文档内容",
                    metadata={"chunk_id": "", "document_id": "", "source": "doc1"},
                )
                return [(doc, 0.05)]

        return None, _VS()

    async def _fake_run_agent_stream(**kwargs):
        agent_calls["n"] += 1
        yield {"kind": "answer_delta", "content": "ok"}

    monkeypatch.setattr(settings, "CHAT_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_RATE_LIMIT_PER_MINUTE", 2)
    monkeypatch.setattr(redis_client, "get_cache_redis", lambda: fake_redis)
    monkeypatch.setattr(chat_service, "build_retriever", _fake_build_retriever)
    monkeypatch.setattr(agent_runner, "run_agent_stream", _fake_run_agent_stream)

    body = {"kb_id": kb_id, "question": "hi", "conversation_id": None}

    r1 = auth_client.post("/api/v1/chat", json=body)
    assert r1.status_code == 200, r1.text
    r2 = auth_client.post("/api/v1/chat", json=body)
    assert r2.status_code == 200, r2.text
    assert agent_calls["n"] == 2
    retrieve_before_block = retrieve_calls["n"]
    assert retrieve_before_block >= 1

    r3 = auth_client.post("/api/v1/chat", json=body)
    assert r3.status_code == 429
    err = r3.json()
    assert err["error_code"] == "RATE_LIMITED"
    assert agent_calls["n"] == 2, "超限请求不得再调用模型"
    assert retrieve_calls["n"] == retrieve_before_block, "超限请求不得再检索"
