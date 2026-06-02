"""Live connectivity checks for Embedding / LLM providers."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(_BACKEND_DIR / ".env", override=False)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION") != "1",
        reason="live API test; set RUN_INTEGRATION=1",
    ),
]


def _require_env(*names: str) -> None:
    missing = [n for n in names if not (os.getenv(n) or "").strip()]
    if missing:
        pytest.skip(f"missing env: {', '.join(missing)}")


def test_embedding_api_returns_vector():
    """SiliconFlow / OpenAI-compatible embedding: string input → vector."""
    _require_env("EMBEDDING_API_KEY", "EMBEDDING_BASE_URL")
    from docpaws.infra.embedding.client import create_embeddings

    vec = create_embeddings().embed_query("ping")
    assert isinstance(vec, list)
    assert len(vec) > 0
    assert all(isinstance(x, float) for x in vec[:3])


def test_llm_api_returns_text():
    """DeepSeek / OpenAI-compatible chat: minimal prompt → non-empty reply."""
    cfg_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    cfg_url = os.getenv("DEEPSEEK_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    if not (cfg_key or "").strip() or not (cfg_url or "").strip():
        pytest.skip("missing env: DEEPSEEK_API_KEY/OPENAI_API_KEY and DEEPSEEK_BASE_URL/OPENAI_BASE_URL")

    from docpaws.usecases.chat_llm import create_chat_llm

    resp = create_chat_llm().invoke("只回复：ok")
    text = (getattr(resp, "content", None) or "").strip()
    assert text
