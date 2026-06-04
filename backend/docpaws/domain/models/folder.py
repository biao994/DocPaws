"""
知识库文件夹表
"""
from datetime import datetime
from uuid import uuid4

from docpaws.domain.datetime_utils import utc_now

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid4().hex


class KbFolder(SQLModel, table=True):
    """知识库内文件夹；parent_id 为空表示 KB 根下的一级目录"""
    __tablename__ = "kb_folder"
    __table_args__ = (
        UniqueConstraint("kb_id", "parent_id", "name", name="unique_kb_folder_parent_name"),
    )

    id: str = Field(default_factory=_uuid, primary_key=True)
    kb_id: str = Field(index=True)
    parent_id: str | None = Field(default=None, index=True, foreign_key="kb_folder.id")
    name: str = Field(max_length=200)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
