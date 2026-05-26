"""
对话问答 DTO
"""
from typing import List, Literal
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """问答请求"""
    kb_id: str
    question: str
    conversation_id: str | None = None
    document_id: str | None = None
    folder_id: str | None = None
    chat_mode: Literal["fast", "deep"] = Field(
        default="fast",
        description="fast=快速（无思考过程展示）；deep=深度（流式展示思考过程）",
    )


class Citation(BaseModel):
    """引用信息"""
    chunk_id: str
    document_id: str
    page_no: int | None = None
    snippet: str
    source: str | None = None
