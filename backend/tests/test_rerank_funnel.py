"""统一检索漏斗：放大召回 → L2 → rerank → 截 search_k（issue 02）。"""
from __future__ import annotations

from docpaws.domain.services.rerank import RerankHit
from docpaws.usecases.chat_service import (
    _retrieval_cache_key,
    retrieve_docs_with_retry,
    retrieve_scoped_docs_cached,
)


class _FakeDoc:
    def __init__(self, page_content: str, metadata: dict | None = None):
        self.page_content = page_content
        self.metadata = metadata or {}


class _FakeRedis:
    def __init__(self):
        self._kv: dict[str, bytes] = {}

    def get(self, key: str):
        return self._kv.get(key)

    def set(self, key: str, value: bytes, ex: int | None = None, nx: bool | None = None):
        if nx and key in self._kv:
            return False
        self._kv[key] = value
        return True


def _enable_fake_rerank(monkeypatch, *, boost: str = "金标", retrieve_k: int = 20):
    import docpaws.settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "RERANK_ENABLED", True)
    monkeypatch.setattr(settings_mod.settings, "RERANK_PROVIDER", "fake")
    monkeypatch.setattr(settings_mod.settings, "RERANK_FAKE_BOOST_SUBSTRING", boost)
    monkeypatch.setattr(settings_mod.settings, "RERANK_RETRIEVE_K", retrieve_k)
    monkeypatch.setattr(settings_mod.settings, "RERANK_MODEL", "fake-model")
    monkeypatch.setattr(settings_mod.settings, "RETRIEVAL_MAX_DISTANCE", 0.5)


def test_rerank_funnel_expands_k_reranks_and_truncates(monkeypatch):
    _enable_fake_rerank(monkeypatch, boost="金标", retrieve_k=10)
    seen = {}

    class _VS:
        def similarity_search_with_score(self, question, k=5, filter=None, fetch_k=20, **kwargs):
            seen["k"] = k
            # FAISS 序：金标在末尾
            return [
                (_FakeDoc("无关1", {"chunk_id": "1"}), 0.1),
                (_FakeDoc("无关2", {"chunk_id": "2"}), 0.2),
                (_FakeDoc("无关3", {"chunk_id": "3"}), 0.3),
                (_FakeDoc("含金标目标", {"chunk_id": "gold"}), 0.4),
            ]

    docs = retrieve_docs_with_retry(_VS(), "q", search_k=2)
    assert seen["k"] == 10
    assert len(docs) == 2
    assert docs[0].metadata["chunk_id"] == "gold"
    assert docs[0].page_content == "含金标目标"


def test_rerank_disabled_uses_search_k_and_faiss_order(monkeypatch):
    import docpaws.settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "RERANK_ENABLED", False)
    monkeypatch.setattr(settings_mod.settings, "RETRIEVAL_MAX_DISTANCE", 0)
    seen = {}

    class _VS:
        def similarity_search_with_score(self, question, k=5, filter=None, fetch_k=20, **kwargs):
            seen["k"] = k
            return [
                (_FakeDoc("a", {"chunk_id": "a"}), 0.1),
                (_FakeDoc("b", {"chunk_id": "b"}), 0.2),
                (_FakeDoc("c", {"chunk_id": "c"}), 0.3),
            ]

    docs = retrieve_docs_with_retry(_VS(), "q", search_k=2)
    assert seen["k"] == 2
    assert [d.metadata["chunk_id"] for d in docs] == ["a", "b"]


def test_empty_after_l2_returns_empty_without_rerank(monkeypatch):
    _enable_fake_rerank(monkeypatch)
    calls = {"n": 0}

    class _Boom:
        def rerank(self, query, documents):
            calls["n"] += 1
            raise AssertionError("should not rerank empty candidates")

    monkeypatch.setattr(
        "docpaws.usecases.chat_service.create_reranker",
        lambda: _Boom(),
    )
    import docpaws.settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "RETRIEVAL_MAX_DISTANCE", 0.05)

    class _VS:
        def similarity_search_with_score(self, question, k=5, filter=None, fetch_k=20, **kwargs):
            return [(_FakeDoc("far", {"chunk_id": "x"}), 0.9)]

    docs = retrieve_docs_with_retry(_VS(), "q", search_k=5)
    assert docs == []
    assert calls["n"] == 0


def test_rerank_error_degrades_to_faiss_order_truncated(monkeypatch):
    _enable_fake_rerank(monkeypatch, retrieve_k=8)

    class _Boom:
        def rerank(self, query, documents):
            raise RuntimeError("upstream timeout")

    monkeypatch.setattr(
        "docpaws.usecases.chat_service.create_reranker",
        lambda: _Boom(),
    )

    class _VS:
        def similarity_search_with_score(self, question, k=5, filter=None, fetch_k=20, **kwargs):
            return [
                (_FakeDoc(f"d{i}", {"chunk_id": str(i)}), 0.1 * (i + 1))
                for i in range(6)
            ]

    docs = retrieve_docs_with_retry(_VS(), "q", search_k=3)
    assert len(docs) == 3
    assert [d.metadata["chunk_id"] for d in docs] == ["0", "1", "2"]


def test_cache_key_isolates_rerank_on_off(monkeypatch):
    import docpaws.settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "RERANK_ENABLED", False)
    monkeypatch.setattr(settings_mod.settings, "RERANK_PROVIDER", "fake")
    monkeypatch.setattr(settings_mod.settings, "RERANK_MODEL", "m1")
    monkeypatch.setattr(settings_mod.settings, "RERANK_RETRIEVE_K", 20)
    off_key = _retrieval_cache_key(
        kb_id="kb",
        artifact_id="a",
        search_k=5,
        question_norm="q",
        scope_token="kb:",
    )
    # 关闭时不插入 rerank 段，与现网 key 形状兼容
    assert ":on:" not in off_key
    assert ":off:" not in off_key
    monkeypatch.setattr(settings_mod.settings, "RERANK_ENABLED", True)
    on_key = _retrieval_cache_key(
        kb_id="kb",
        artifact_id="a",
        search_k=5,
        question_norm="q",
        scope_token="kb:",
    )
    assert off_key != on_key
    assert ":on:fake:m1:20:" in on_key


def test_cached_list_is_post_rerank_truncated(monkeypatch):
    _enable_fake_rerank(monkeypatch, boost="金标", retrieve_k=10)
    fake_redis = _FakeRedis()

    class _VS:
        def similarity_search_with_score(self, question, k=5, filter=None, fetch_k=20, **kwargs):
            return [
                (_FakeDoc("无关", {"chunk_id": "1"}), 0.1),
                (_FakeDoc("含金标", {"chunk_id": "gold"}), 0.2),
                (_FakeDoc("无关2", {"chunk_id": "3"}), 0.3),
            ]

    docs = retrieve_scoped_docs_cached(
        kb_id="kb",
        question="q",
        search_k=1,
        metadata_filter=None,
        vectorstore=_VS(),
        cache_redis=fake_redis,
        artifact_id="art",
        scope_token="kb:",
    )
    assert len(docs) == 1
    assert docs[0].metadata["chunk_id"] == "gold"
    assert len(fake_redis._kv) == 1
    cached_raw = next(iter(fake_redis._kv.values()))
    assert b"gold" in cached_raw
    assert b'"chunk_id":"1"' not in cached_raw.replace(b" ", b"")
