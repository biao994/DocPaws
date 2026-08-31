"""Fake rerank：含约定子串的候选靠前，供单测 / CI，不打外网。"""
from __future__ import annotations

from typing import Sequence

from docpaws.domain.services.rerank import RerankHit


class FakeReranker:
    def __init__(self, *, boost_substring: str = ""):
        self.boost_substring = (boost_substring or "").strip()

    def rerank(self, query: str, documents: Sequence[str]) -> list[RerankHit]:
        needle = self.boost_substring
        boosted: list[RerankHit] = []
        rest: list[RerankHit] = []
        for i, text in enumerate(documents):
            if needle and needle in (text or ""):
                boosted.append(RerankHit(index=i, score=1.0))
            else:
                rest.append(RerankHit(index=i, score=0.0))
        return boosted + rest
