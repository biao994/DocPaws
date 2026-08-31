"""A-class 排序验收：fake 开启后 gold 进 final_k；默认关闭不改基线（issue 04）。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from docpaws.usecases.chat_service import retrieve_docs_with_retry

# probe 中 gold_rank≥3 的题；must_contain 与 golden_20 对齐
A_CLASS = [
    ("q07", "contact@xinghe-tech"),
    ("q13", "FastAPI"),
    ("q15", "INDEX_DIR"),
    ("q16", "SQLite"),
    ("q20", "Cookie"),
]

FINAL_K = 5
RETRIEVE_K = 10


class _FakeDoc:
    def __init__(self, page_content: str, metadata: dict | None = None):
        self.page_content = page_content
        self.metadata = metadata or {}


def _baseline_pairs(gold_token: str):
    """模拟 A-class：无关片段在前，gold 排在第 7（> final_k）。"""
    pairs = []
    for i in range(1, 7):
        pairs.append((_FakeDoc(f"无关片段 {i}", {"chunk_id": f"n{i}"}), 0.1 * i))
    pairs.append((_FakeDoc(f"含答案关键词 {gold_token} 的片段", {"chunk_id": "gold"}), 0.7))
    pairs.append((_FakeDoc("更远无关", {"chunk_id": "n8"}), 0.8))
    return pairs


@pytest.mark.parametrize("qid,gold_token", A_CLASS)
def test_a_class_fake_rerank_lifts_gold_into_final_k(monkeypatch, qid, gold_token):
    import docpaws.settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "RERANK_ENABLED", True)
    monkeypatch.setattr(settings_mod.settings, "RERANK_PROVIDER", "fake")
    monkeypatch.setattr(settings_mod.settings, "RERANK_FAKE_BOOST_SUBSTRING", gold_token)
    monkeypatch.setattr(settings_mod.settings, "RERANK_RETRIEVE_K", RETRIEVE_K)
    monkeypatch.setattr(settings_mod.settings, "RETRIEVAL_MAX_DISTANCE", 0)

    pairs = _baseline_pairs(gold_token)

    class _VS:
        def similarity_search_with_score(self, question, k=5, filter=None, fetch_k=20, **kwargs):
            return pairs[:k]

    docs = retrieve_docs_with_retry(_VS(), f"{qid} question", search_k=FINAL_K)
    assert len(docs) == FINAL_K
    assert docs[0].metadata["chunk_id"] == "gold"
    assert gold_token in docs[0].page_content


@pytest.mark.parametrize("qid,gold_token", A_CLASS)
def test_a_class_rerank_off_keeps_faiss_order_gold_out_of_final_k(monkeypatch, qid, gold_token):
    import docpaws.settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "RERANK_ENABLED", False)
    monkeypatch.setattr(settings_mod.settings, "RETRIEVAL_MAX_DISTANCE", 0)

    pairs = _baseline_pairs(gold_token)

    class _VS:
        def similarity_search_with_score(self, question, k=5, filter=None, fetch_k=20, **kwargs):
            return pairs[:k]

    docs = retrieve_docs_with_retry(_VS(), f"{qid} question", search_k=FINAL_K)
    assert len(docs) == FINAL_K
    assert all(d.metadata["chunk_id"] != "gold" for d in docs)
    assert docs[0].metadata["chunk_id"] == "n1"


def test_golden_must_contain_tokens_cover_a_class():
    """夹具与 golden_20 对齐，避免断言关键词漂移。"""
    golden = Path(__file__).resolve().parents[2] / "eval" / "golden_20.jsonl"
    by_id = {}
    for line in golden.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        by_id[row["id"]] = row
    for qid, token in A_CLASS:
        assert qid in by_id
        assert token in (by_id[qid].get("must_contain") or [])
