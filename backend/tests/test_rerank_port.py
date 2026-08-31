"""Rerank 端口 / 工厂 / fake·noop 单测（issue 01）。"""
from __future__ import annotations


def test_fake_reranker_boosts_documents_containing_keyword():
    from docpaws.infra.rerank.fake import FakeReranker

    reranker = FakeReranker(boost_substring="金标")
    docs = ["无关片段 A", "含金标的目标片段", "无关片段 B"]
    ranked = reranker.rerank("任意问题", docs)
    assert [r.index for r in ranked] == [1, 0, 2]
    assert ranked[0].score >= ranked[1].score


def test_noop_reranker_preserves_input_order():
    from docpaws.infra.rerank.noop import NoopReranker

    docs = ["a", "b", "c"]
    ranked = NoopReranker().rerank("q", docs)
    assert [r.index for r in ranked] == [0, 1, 2]


def test_create_reranker_disabled_returns_none(monkeypatch):
    import docpaws.settings as settings_mod
    from docpaws.infra.rerank import create_reranker

    monkeypatch.setattr(settings_mod.settings, "RERANK_ENABLED", False)
    monkeypatch.setattr(settings_mod.settings, "RERANK_PROVIDER", "fake")
    assert create_reranker() is None


def test_create_reranker_selects_fake_when_enabled(monkeypatch):
    import docpaws.settings as settings_mod
    from docpaws.infra.rerank import create_reranker
    from docpaws.infra.rerank.fake import FakeReranker

    monkeypatch.setattr(settings_mod.settings, "RERANK_ENABLED", True)
    monkeypatch.setattr(settings_mod.settings, "RERANK_PROVIDER", "fake")
    monkeypatch.setattr(settings_mod.settings, "RERANK_FAKE_BOOST_SUBSTRING", "金标")
    client = create_reranker()
    assert isinstance(client, FakeReranker)
    ranked = client.rerank("q", ["x", "金标片段", "y"])
    assert ranked[0].index == 1
