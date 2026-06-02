"""
Embedding 客户端封装

统一 Embedding 调用接口，支持供应商切换。
"""
from typing import Any

from langchain_openai import OpenAIEmbeddings

from docpaws.config import get_default_config


class OpenAICompatibleEmbeddings(OpenAIEmbeddings):
    """向 OpenAI 兼容 API 发送原始字符串，避免 tiktoken token ID 数组被拒。"""

    def _get_len_safe_embeddings(
        self,
        texts: list[str],
        *,
        engine: str,
        chunk_size: int | None = None,
        **kwargs: Any,
    ) -> list[list[float]]:
        if not texts:
            return []
        client_kwargs = {**self._invocation_params, **kwargs}
        batch_size = chunk_size or self.chunk_size
        embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = self.client.create(input=batch, **client_kwargs)
            if not isinstance(response, dict):
                response = response.model_dump()
            embeddings.extend(item["embedding"] for item in response["data"])
        return embeddings


def create_embeddings(config: dict | None = None):
    """
    创建 OpenAI 兼容的 Embedding 实例

    Args:
        config: 配置字典，默认使用 get_default_config()
    """
    cfg = config or get_default_config()
    return OpenAICompatibleEmbeddings(
        model=cfg.get("embedding_model", "text-embedding-3-small"),
        chunk_size=cfg.get("embedding_chunk_size", 200),
        timeout=cfg.get("embedding_timeout", 120),
        api_key=cfg.get("embedding_api_key"),
        base_url=cfg.get("embedding_base_url"),
    )
