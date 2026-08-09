"""问答按用户限流：第一刀 —— 开启后超次数 → 429，且不碰模型。"""


class _FakeDoc:
    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata


class _FakeRedis:
    """假 Redis：限流用到的 incr/expire/set/delete/sadd 等。"""

    def __init__(self):
        self._kv: dict[str, int | bytes] = {}
        self._ttl: dict[str, int] = {}
        self._sets: dict[str, set[str]] = {}

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

    def delete(self, *keys: str) -> int:
        n = 0
        for key in keys:
            if key in self._kv:
                del self._kv[key]
                n += 1
            elif key in self._sets:
                n += 1
            self._ttl.pop(key, None)
            self._sets.pop(key, None)
        return n

    def sadd(self, key: str, *values) -> int:
        s = self._sets.setdefault(key, set())
        before = len(s)
        for v in values:
            s.add(v.decode() if isinstance(v, bytes) else str(v))
        return len(s) - before

    def srem(self, key: str, *values) -> int:
        s = self._sets.get(key)
        if not s:
            return 0
        n = 0
        for v in values:
            item = v.decode() if isinstance(v, bytes) else str(v)
            if item in s:
                s.discard(item)
                n += 1
        if not s:
            self._sets.pop(key, None)
        return n

    def smembers(self, key: str) -> set:
        return set(self._sets.get(key, set()))

    def scard(self, key: str) -> int:
        return len(self._sets.get(key, set()))

    def exists(self, key: str) -> int:
        return 1 if key in self._kv or key in self._sets else 0


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


def test_chat_concurrent_limit_returns_429_without_calling_llm(
    auth_client, db_session, monkeypatch, tmp_path
):
    """开启限流 + 假 Redis：同用户已占满并发槽 → 429 CONCURRENT_LIMITED，且不调模型。"""
    from sqlmodel import select

    from docpaws.domain.models.user import User
    from docpaws.infra.rate_limit.chat_rate_limiter import try_acquire_chat_concurrent_slot
    from docpaws.settings import settings

    kb_id = _seed_ready_kb(auth_client, db_session, tmp_path)
    user = db_session.exec(select(User)).first()
    assert user is not None

    fake_redis = _FakeRedis()
    agent_calls = {"n": 0}

    import docpaws.infra.cache.redis_client as redis_client
    import docpaws.usecases.chat_agent_runner as agent_runner
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
        agent_calls["n"] += 1
        yield {"kind": "answer_delta", "content": "ok"}

    monkeypatch.setattr(settings, "CHAT_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_RATE_LIMIT_PER_MINUTE", 100)
    monkeypatch.setattr(settings, "CHAT_CONCURRENT_LIMIT", 2)
    monkeypatch.setattr(settings, "CHAT_CONCURRENT_TTL_SECONDS", 600)
    monkeypatch.setattr(redis_client, "get_cache_redis", lambda: fake_redis)
    monkeypatch.setattr(chat_service, "build_retriever", _fake_build_retriever)
    monkeypatch.setattr(agent_runner, "run_agent_stream", _fake_run_agent_stream)

    assert try_acquire_chat_concurrent_slot(user.id, "hold-1", fake_redis)
    assert try_acquire_chat_concurrent_slot(user.id, "hold-2", fake_redis)

    r = auth_client.post(
        "/api/v1/chat",
        json={"kb_id": kb_id, "question": "hi", "conversation_id": None},
    )
    assert r.status_code == 429
    assert r.json()["error_code"] == "CONCURRENT_LIMITED"
    assert agent_calls["n"] == 0, "并发满时不得调用模型"


def _patch_chat_happy_path(monkeypatch, settings, fake_redis=None, *, agent_impl=None):
    """注入假 Redis（或 None=模拟不可用）、检索与 Agent。默认打开限流开关。"""
    import docpaws.infra.cache.redis_client as redis_client
    import docpaws.usecases.chat_agent_runner as agent_runner
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

    async def _default_agent(**kwargs):
        yield {"kind": "answer_delta", "content": "ok"}

    monkeypatch.setattr(settings, "CHAT_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_RATE_LIMIT_PER_MINUTE", 100)
    monkeypatch.setattr(settings, "CHAT_CONCURRENT_LIMIT", 2)
    monkeypatch.setattr(settings, "CHAT_CONCURRENT_TTL_SECONDS", 600)
    monkeypatch.setattr(redis_client, "get_cache_redis", lambda: fake_redis)
    monkeypatch.setattr(chat_service, "build_retriever", _fake_build_retriever)
    monkeypatch.setattr(agent_runner, "run_agent_stream", agent_impl or _default_agent)


def test_chat_concurrent_slot_released_after_answer(
    auth_client, db_session, monkeypatch, tmp_path
):
    """并发上限 2：三次串行问答均成功，说明答完会释放名额。"""
    from docpaws.settings import settings

    kb_id = _seed_ready_kb(auth_client, db_session, tmp_path)
    fake_redis = _FakeRedis()
    _patch_chat_happy_path(monkeypatch, settings, fake_redis)

    body = {"kb_id": kb_id, "question": "hi", "conversation_id": None}
    for i in range(3):
        r = auth_client.post("/api/v1/chat", json=body)
        assert r.status_code == 200, f"第 {i + 1} 次应释放后可再进: {r.text}"


def test_chat_concurrent_slot_released_after_error(
    auth_client, db_session, monkeypatch, tmp_path
):
    """生成中出错也会释放并发槽，后续串行问答仍可进入。"""
    from docpaws.settings import settings

    kb_id = _seed_ready_kb(auth_client, db_session, tmp_path)
    fake_redis = _FakeRedis()
    calls = {"n": 0}

    async def _flaky_agent(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        yield {"kind": "answer_delta", "content": "recovered"}

    _patch_chat_happy_path(monkeypatch, settings, fake_redis, agent_impl=_flaky_agent)

    body = {"kb_id": kb_id, "question": "hi", "conversation_id": None}
    auth_client.post("/api/v1/chat", json=body)  # 出错路径，触发 finally 释放
    for i in range(3):
        r = auth_client.post("/api/v1/chat", json=body)
        assert r.status_code == 200, f"出错释放后第 {i + 1} 次应成功: {r.text}"


def test_chat_concurrent_lease_sets_ttl(monkeypatch):
    """成功占槽时给成员集与租约键打上可配 TTL。"""
    from docpaws.infra.rate_limit.chat_rate_limiter import try_acquire_chat_concurrent_slot
    from docpaws.settings import settings

    fake_redis = _FakeRedis()
    monkeypatch.setattr(settings, "CHAT_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_CONCURRENT_LIMIT", 2)
    monkeypatch.setattr(settings, "CHAT_CONCURRENT_TTL_SECONDS", 600)

    assert try_acquire_chat_concurrent_slot("u1", "lease-a", fake_redis)
    assert fake_redis._ttl.get("chat:conc:u1") == 600
    assert fake_redis._ttl.get("chat:conc:lease:u1:lease-a") == 600


def test_chat_concurrent_expired_lease_frees_slot(monkeypatch):
    """租约键过期后，下次 acquire 会清掉虚占，名额可再拿。"""
    from docpaws.infra.rate_limit.chat_rate_limiter import try_acquire_chat_concurrent_slot
    from docpaws.settings import settings

    fake_redis = _FakeRedis()
    monkeypatch.setattr(settings, "CHAT_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_CONCURRENT_LIMIT", 2)
    monkeypatch.setattr(settings, "CHAT_CONCURRENT_TTL_SECONDS", 600)

    assert try_acquire_chat_concurrent_slot("u1", "a", fake_redis)
    assert try_acquire_chat_concurrent_slot("u1", "b", fake_redis)
    assert not try_acquire_chat_concurrent_slot("u1", "c", fake_redis)

    # 模拟 TTL 到期：租约键消失，成员集仍残留
    del fake_redis._kv["chat:conc:lease:u1:a"]
    del fake_redis._kv["chat:conc:lease:u1:b"]

    assert try_acquire_chat_concurrent_slot("u1", "c", fake_redis)


def test_minute_limit_releases_concurrent_slot(
    auth_client, db_session, monkeypatch, tmp_path
):
    """次数超限拒答前会归还刚占的并发槽。"""
    from sqlmodel import select

    from docpaws.domain.models.user import User
    from docpaws.infra.rate_limit.chat_rate_limiter import try_acquire_chat_concurrent_slot
    from docpaws.settings import settings

    kb_id = _seed_ready_kb(auth_client, db_session, tmp_path)
    user = db_session.exec(select(User)).first()
    assert user is not None

    fake_redis = _FakeRedis()
    _patch_chat_happy_path(monkeypatch, settings, fake_redis)
    monkeypatch.setattr(settings, "CHAT_RATE_LIMIT_PER_MINUTE", 1)

    body = {"kb_id": kb_id, "question": "hi", "conversation_id": None}
    assert auth_client.post("/api/v1/chat", json=body).status_code == 200
    r2 = auth_client.post("/api/v1/chat", json=body)
    assert r2.status_code == 429
    assert r2.json()["error_code"] == "RATE_LIMITED"

    assert try_acquire_chat_concurrent_slot(user.id, "a", fake_redis)
    assert try_acquire_chat_concurrent_slot(user.id, "b", fake_redis)


def test_chat_rate_limit_unavailable_when_redis_missing(
    auth_client, db_session, monkeypatch, tmp_path
):
    """开启限流但 Redis 不可用（None）→ 503 RATE_LIMIT_UNAVAILABLE，不打模型。"""
    from docpaws.settings import settings

    kb_id = _seed_ready_kb(auth_client, db_session, tmp_path)
    agent_calls = {"n": 0}

    async def _fake_run_agent_stream(**kwargs):
        agent_calls["n"] += 1
        yield {"kind": "answer_delta", "content": "ok"}

    _patch_chat_happy_path(monkeypatch, settings, fake_redis=None, agent_impl=_fake_run_agent_stream)

    r = auth_client.post(
        "/api/v1/chat",
        json={"kb_id": kb_id, "question": "hi", "conversation_id": None},
    )
    assert r.status_code == 503
    assert r.json()["error_code"] == "RATE_LIMIT_UNAVAILABLE"
    assert agent_calls["n"] == 0


class _BrokenRedis:
    """模拟 Redis 已注入但操作失败（连不上）。"""

    def smembers(self, key):
        raise ConnectionError("redis down")

    def incr(self, key):
        raise ConnectionError("redis down")


def test_chat_rate_limit_unavailable_when_redis_errors(
    auth_client, db_session, monkeypatch, tmp_path
):
    """开启限流但 Redis 操作抛错 → 503，不打模型。"""
    from docpaws.settings import settings

    kb_id = _seed_ready_kb(auth_client, db_session, tmp_path)
    agent_calls = {"n": 0}

    async def _fake_run_agent_stream(**kwargs):
        agent_calls["n"] += 1
        yield {"kind": "answer_delta", "content": "ok"}

    _patch_chat_happy_path(
        monkeypatch, settings, fake_redis=_BrokenRedis(), agent_impl=_fake_run_agent_stream
    )

    r = auth_client.post(
        "/api/v1/chat",
        json={"kb_id": kb_id, "question": "hi", "conversation_id": None},
    )
    assert r.status_code == 503
    assert r.json()["error_code"] == "RATE_LIMIT_UNAVAILABLE"
    assert agent_calls["n"] == 0


def test_chat_rate_limit_disabled_allows_all(
    auth_client, db_session, monkeypatch, tmp_path
):
    """开关关闭时，即使无 Redis、阈值设得很紧，连问也不限流。"""
    from docpaws.settings import settings

    kb_id = _seed_ready_kb(auth_client, db_session, tmp_path)
    agent_calls = {"n": 0}

    async def _fake_run_agent_stream(**kwargs):
        agent_calls["n"] += 1
        yield {"kind": "answer_delta", "content": "ok"}

    _patch_chat_happy_path(monkeypatch, settings, fake_redis=None, agent_impl=_fake_run_agent_stream)
    monkeypatch.setattr(settings, "CHAT_RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "CHAT_RATE_LIMIT_PER_MINUTE", 1)
    monkeypatch.setattr(settings, "CHAT_CONCURRENT_LIMIT", 1)

    body = {"kb_id": kb_id, "question": "hi", "conversation_id": None}
    for i in range(5):
        r = auth_client.post("/api/v1/chat", json=body)
        assert r.status_code == 200, f"关闭限流后第 {i + 1} 次应放行: {r.text}"
    assert agent_calls["n"] == 5
