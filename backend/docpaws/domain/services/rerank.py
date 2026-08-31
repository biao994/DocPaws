"""Rerank 端口：query + 候选文本 → 按相关分排序的索引结果。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class RerankHit:
    """单个重排结果：原候选下标 + 相关分（越高越相关）。"""

    index: int
    score: float


class Reranker(Protocol):
    def rerank(self, query: str, documents: Sequence[str]) -> list[RerankHit]:
        """返回按相关分降序的命中列表；须覆盖全部输入下标。"""
        ...
