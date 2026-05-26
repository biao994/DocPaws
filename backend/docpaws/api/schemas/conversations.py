"""
会话 / 消息 / 反馈 DTO
"""
from datetime import datetime
from typing import List
from pydantic import BaseModel


class CitationData(BaseModel):
    chunk_id: str
    document_id: str | None = None
    page_no: int | None = None
    snippet: str = ""
    source: str | None = None


class MessageData(BaseModel):
    id: str
    role: str
    content: str
    answer_id: str | None = None
    created_at: datetime
    citations: List[CitationData] = []


class ConversationData(BaseModel):
    id: str
    kb_id: str
    title: str
    scope_type: str = "kb"
    scope_id: str | None = None
    created_at: datetime
    updated_at: datetime
    messages: List[MessageData] = []
