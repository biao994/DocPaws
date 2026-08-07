"""联网检索基础设施：You.com Search API 客户端（外部 I/O 层）。"""
from docpaws.infra.websearch.youcom_client import (
    web_search_available,
    youcom_web_search,
)

__all__ = ["web_search_available", "youcom_web_search"]
