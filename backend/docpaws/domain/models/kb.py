"""
知识库表
"""
from datetime import datetime

from docpaws.domain.datetime_utils import utc_now
from docpaws.domain.models.user import _uuid

from sqlmodel import Field, SQLModel


class KnowledgeBase(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str = Field(default="")
    description: str = Field(default="")
    owner_user_id: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
