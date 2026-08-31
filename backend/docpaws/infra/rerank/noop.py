"""Noop rerank：保持输入顺序，不调用远端。"""
from __future__ import annotations

from typing import Sequence

from docpaws.domain.services.rerank import RerankHit


class NoopReranker:
    def rerank(self, query: str, documents: Sequence[str]) -> list[RerankHit]:
        return [RerankHit(index=i, score=0.0) for i in range(len(documents))]
