"""
LLM / Embedding 统一配置
"""
import os
from typing import Dict, Any


def get_default_config() -> Dict[str, Any]:
    """获取默认配置（LLM + Embedding + 分块参数）"""
    llm_api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    llm_base_url = os.getenv("DEEPSEEK_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    llm_model = os.getenv("LLM_MODEL", "deepseek-v4-flash")

    embedding_api_key = os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY")
    embedding_base_url = os.getenv("EMBEDDING_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    return {
        "chunk_size": 500,
        "chunk_overlap": 100,
        "search_k": 5,
        "memory_window": 10,
        "temperature": 0.1,
        # LLM
        "model": llm_model,
        "llm_api_key": llm_api_key,
        "llm_base_url": llm_base_url,
        # Embedding
        "embedding_model": embedding_model,
        "embedding_api_key": embedding_api_key,
        "embedding_base_url": embedding_base_url,
        "embedding_chunk_size": 32,
        "embedding_timeout": 120,
        "llm_timeout": 30,
        "thinking_timeout": 90,
        "thinking_max_tokens": 2048,
        "llm_max_retries": 3,
        "vector_store_path": "./faiss_index",
        "max_tokens": 1000,
    }


def merge_config(user_config: Dict[str, Any] = None) -> Dict[str, Any]:
    default_config = get_default_config()
    if user_config is None:
        return default_config
    return {**default_config, **user_config}
