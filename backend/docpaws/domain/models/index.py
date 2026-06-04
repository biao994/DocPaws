"""
索引任务 + 索引产物 + 检索记录 + 答案 表（流程/产物表族）
"""
from datetime import datetime
from uuid import uuid4

from docpaws.domain.datetime_utils import utc_now
from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid4().hex


# ── 流程表族 ──

class IndexJob(SQLModel, table=True):
    """索引构建任务表（KB 级：一次任务覆盖整个知识库的 manifest diff + 向量重建）"""
    id: str = Field(default_factory=_uuid, primary_key=True)
    kb_id: str = Field(index=True)
    status: str = Field(default="queued", index=True, description="queued/running/succeeded/failed")
    progress: int = Field(default=0)
    error_message: str | None = Field(default=None)
    idempotency_key: str = Field(index=True, unique=True)
    diff_summary: dict | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)


# ── 产物表族 ──

class IndexArtifact(SQLModel, table=True):
    """索引产物表 - 可复用、可回滚"""
    id: str = Field(default_factory=_uuid, primary_key=True)
    kb_id: str = Field(index=True)
    version: int = Field(default=1)
    index_path: str = Field()
    index_job_id: str = Field(index=True)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)


class IndexArtifactManifest(SQLModel, table=True):
    """某版 IndexArtifact 包含的文档清单（真相源，用于 diff / 复盘）"""

    id: str = Field(default_factory=_uuid, primary_key=True)
    artifact_id: str = Field(index=True, foreign_key="indexartifact.id")
    document_id: str = Field(index=True)
    content_hash: str = Field(index=True)
    chunk_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=utc_now)


class RetrievalRun(SQLModel, table=True):
    """检索过程记录"""
    id: str = Field(default_factory=_uuid, primary_key=True)
    kb_id: str = Field(index=True)
    conversation_id: str = Field(index=True)
    question_message_id: str = Field(index=True)
    query_text: str = Field()
    top_k: int = Field(default=5)
    hit_chunks: str = Field(default="[]", sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)


class Answer(SQLModel, table=True):
    """答案产物表 - 支持多版本"""
    id: str = Field(default_factory=_uuid, primary_key=True)
    conversation_id: str = Field(index=True)
    question_message_id: str = Field(index=True)
    version: int = Field(default=1)
    is_current: bool = Field(default=True)
    answer_text: str = Field()
    citations: str = Field(default="[]", sa_column=Column(JSON))
    model_name: str = Field(default="deepseek-response")
    created_at: datetime = Field(default_factory=utc_now)
