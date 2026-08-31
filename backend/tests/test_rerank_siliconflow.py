"""SiliconFlow Rerank provider 单测（mock HTTP，不打外网）。"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


def test_siliconflow_reranker_posts_expected_body_and_orders_by_score():
    from docpaws.infra.rerank.siliconflow import SiliconFlowReranker

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "rerank-test",
        "results": [
            {"index": 2, "relevance_score": 0.9},
            {"index": 0, "relevance_score": 0.5},
            {"index": 1, "relevance_score": 0.1},
        ],
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("docpaws.infra.rerank.siliconflow.httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.post.return_value = mock_resp
        client_cls.return_value = client

        reranker = SiliconFlowReranker(
            api_key="sk-test",
            base_url="https://api.siliconflow.cn/v1",
            model="BAAI/bge-reranker-v2-m3",
            timeout_seconds=5,
        )
        ranked = reranker.rerank("Apple", ["banana", "vegetable", "apple"])

    assert [h.index for h in ranked] == [2, 0, 1]
    assert ranked[0].score == pytest.approx(0.9)

    kwargs = client.post.call_args
    url = kwargs.args[0] if kwargs.args else kwargs.kwargs.get("url")
    assert str(url).rstrip("/").endswith("/rerank")
    body = kwargs.kwargs.get("json") or {}
    assert body["model"] == "BAAI/bge-reranker-v2-m3"
    assert body["query"] == "Apple"
    assert body["documents"] == ["banana", "vegetable", "apple"]
    headers = kwargs.kwargs.get("headers") or {}
    assert headers.get("Authorization") == "Bearer sk-test"


def test_create_reranker_selects_siliconflow(monkeypatch):
    import docpaws.settings as settings_mod
    from docpaws.infra.rerank import create_reranker
    from docpaws.infra.rerank.siliconflow import SiliconFlowReranker

    monkeypatch.setattr(settings_mod.settings, "RERANK_ENABLED", True)
    monkeypatch.setattr(settings_mod.settings, "RERANK_PROVIDER", "siliconflow")
    monkeypatch.setattr(settings_mod.settings, "RERANK_API_KEY", "sk-x")
    monkeypatch.setattr(settings_mod.settings, "RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
    client = create_reranker()
    assert isinstance(client, SiliconFlowReranker)


def test_siliconflow_http_error_raises_for_funnel_degrade():
    from docpaws.infra.rerank.siliconflow import SiliconFlowReranker

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.raise_for_status.side_effect = Exception("401 unauthorized")

    with patch("docpaws.infra.rerank.siliconflow.httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.post.return_value = mock_resp
        client_cls.return_value = client

        reranker = SiliconFlowReranker(
            api_key="",
            base_url="https://api.siliconflow.cn/v1",
            model="BAAI/bge-reranker-v2-m3",
        )
        with pytest.raises(Exception):
            reranker.rerank("q", ["a", "b"])
