"""按配置解析 Rerank 实现（关闭则返回 None）。"""
from __future__ import annotations

from docpaws.domain.services.rerank import Reranker
from docpaws.settings import settings


def create_reranker() -> Reranker | None:
    """RERANK_ENABLED=false 时返回 None；否则按 RERANK_PROVIDER 选型。"""
    if not settings.RERANK_ENABLED:
        return None

    provider = (settings.RERANK_PROVIDER or "").strip().lower() or "siliconflow"
    if provider in ("noop", "off", "none"):
        from docpaws.infra.rerank.noop import NoopReranker

        return NoopReranker()
    if provider == "fake":
        from docpaws.infra.rerank.fake import FakeReranker

        return FakeReranker(boost_substring=settings.RERANK_FAKE_BOOST_SUBSTRING or "")
    if provider == "siliconflow":
        from docpaws.infra.rerank.siliconflow import SiliconFlowReranker

        return SiliconFlowReranker(
            api_key=settings.RERANK_API_KEY or "",
            base_url=settings.RERANK_BASE_URL or "https://api.siliconflow.cn/v1",
            model=settings.RERANK_MODEL or "Qwen/Qwen3-Reranker-8B",
            timeout_seconds=float(settings.RERANK_TIMEOUT_SECONDS),
        )
    raise ValueError(f"unsupported RERANK_PROVIDER: {provider}")
