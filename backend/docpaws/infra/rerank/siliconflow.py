"""SiliconFlow 云端 Rerank（OpenAI 兼容 /v1/rerank）。"""
from __future__ import annotations

from typing import Sequence
from urllib.parse import urljoin

import httpx

from docpaws.domain.services.rerank import RerankHit


class SiliconFlowReranker:
    """调用 SiliconFlow Rerank API；失败由检索漏斗降级，本类直接抛错。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.siliconflow.cn/v1",
        model: str = "Qwen/Qwen3-Reranker-8B",
        timeout_seconds: float = 10,
    ):
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or "https://api.siliconflow.cn/v1").rstrip("/") + "/"
        self.model = (model or "Qwen/Qwen3-Reranker-8B").strip()
        self.timeout_seconds = float(timeout_seconds or 10)

    def rerank(self, query: str, documents: Sequence[str]) -> list[RerankHit]:
        if not documents:
            return []
        url = urljoin(self.base_url, "rerank")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "query": query,
            "documents": list(documents),
            "top_n": len(documents),
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results") or []
        hits: list[RerankHit] = []
        seen: set[int] = set()
        for item in results:
            if not isinstance(item, dict):
                continue
            idx = int(item.get("index", -1))
            if idx < 0 or idx >= len(documents) or idx in seen:
                continue
            seen.add(idx)
            score = float(item.get("relevance_score", item.get("score", 0.0)) or 0.0)
            hits.append(RerankHit(index=idx, score=score))

        # 接口若漏下标，按原序补齐，保证覆盖全部候选
        for i in range(len(documents)):
            if i not in seen:
                hits.append(RerankHit(index=i, score=0.0))
        return hits
