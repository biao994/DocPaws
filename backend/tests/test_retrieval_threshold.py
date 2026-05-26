"""检索距离阈值与拒答逻辑单测。"""
from __future__ import annotations

from docpaws.usecases.chat_service import (
    INSUFFICIENT_RETRIEVAL_MSG,
    _filter_scored_pairs,
    docs_from_scored_pairs,
    hit_chunks_from_docs,
    retrieve_docs_with_retry,
    should_skip_retrieval_preflight,
)


class _FakeDoc:
    def __init__(self, metadata: dict | None = None):
        self.page_content = "x"
        self.metadata = metadata or {}


def test_filter_scored_pairs_by_max_distance(monkeypatch):
    import docpaws.settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "RETRIEVAL_MAX_DISTANCE", 0.5)

    pairs = [(_FakeDoc(), 0.2), (_FakeDoc(), 0.8)]
    out = _filter_scored_pairs(pairs)
    assert len(out) == 1
    assert out[0][1] == 0.2


def test_retrieve_docs_with_retry_applies_threshold(monkeypatch):
    import docpaws.settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "RETRIEVAL_MAX_DISTANCE", 0.3)

    class _VS:
        def similarity_search_with_score(self, question, k=5, filter=None, fetch_k=20, **kwargs):
            return [(_FakeDoc({"chunk_id": "a"}), 0.1), (_FakeDoc({"chunk_id": "b"}), 0.9)]

    docs = retrieve_docs_with_retry(_VS(), "q", search_k=5)
    assert len(docs) == 1
    assert docs[0].metadata["_retrieval_score"] == 0.1


def test_hit_chunks_from_docs_includes_score():
    d = _FakeDoc({"chunk_id": "c1", "_retrieval_score": 0.42})
    chunks = hit_chunks_from_docs([d])
    assert chunks == [{"chunk_id": "c1", "score": 0.42}]


def test_should_skip_preflight_for_meta_questions():
    assert should_skip_retrieval_preflight("当前知识库里有几个文档？")
    assert not should_skip_retrieval_preflight("星河科技是哪一年成立的？")


def test_insufficient_message_constant():
    assert "无法基于文档" in INSUFFICIENT_RETRIEVAL_MSG
