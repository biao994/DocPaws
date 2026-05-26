"""
Embedding 客户端封装

统一 Embedding 调用接口，支持供应商切换。
"""
from langchain_openai import OpenAIEmbeddings

from docpaws.config import get_default_config


def create_embeddings(config: dict | None = None):
    """
    创建 OpenAI 兼容的 Embedding 实例

    Args:
        config: 配置字典，默认使用 get_default_config()
    """
    cfg = config or get_default_config()
    return OpenAIEmbeddings(
        model=cfg.get("embedding_model", "text-embedding-3-small"),
        chunk_size=cfg.get("embedding_chunk_size", 200),
        timeout=cfg.get("embedding_timeout", 120),
        api_key=cfg.get("embedding_api_key"),
        base_url=cfg.get("embedding_base_url"),
    )
