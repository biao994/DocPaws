"""
运营表族：用量 / 成本记录
"""
from datetime import datetime
from uuid import uuid4

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid4().hex


class UsageRecord(SQLModel, table=True):
    """用量记录表（一期：每次 chat 流式问答一条，记耗时与成败）"""

    id: str = Field(default_factory=_uuid, primary_key=True)
    request_id: str = Field(index=True)
    kb_id: str | None = Field(default=None, index=True)
    user_id: str | None = Field(default=None, index=True)
    action: str = Field()
    latency_ms: int = Field()
    tokens_in: int = Field(default=0)
    tokens_out: int = Field(default=0)
    cost: float = Field(default=0.0)
    model_name: str = Field(default="")
    error_code: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
