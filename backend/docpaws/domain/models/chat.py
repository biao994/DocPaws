"""
会话 / 消息 / 反馈 表（交互表族）
"""
from datetime import datetime
from uuid import uuid4

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid4().hex


class Conversation(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    kb_id: str = Field(index=True)
    user_id: str = Field(index=True)
    title: str = Field(default="新会话", max_length=100)
    scope_type: str = Field(default="kb", description="kb / folder / file")
    scope_id: str | None = Field(default=None, index=True, description="folder_id 或 document_id；整库为空")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Message(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    conversation_id: str = Field(index=True)
    role: str = Field(description="user/assistant")
    content: str = Field()
    answer_id: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Feedback(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    answer_id: str = Field(index=True)
    user_id: str = Field(index=True)
    rating: str = Field(description="like/dislike")
    comment: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
