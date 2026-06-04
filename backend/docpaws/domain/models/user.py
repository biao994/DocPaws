"""
用户表
"""
from datetime import datetime
from uuid import uuid4

from docpaws.domain.datetime_utils import utc_now

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid4().hex


class User(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    username: str = Field(default="", unique=True)
    email: str = Field(index=True, unique=True)
    password_hash: str = Field(default="")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
