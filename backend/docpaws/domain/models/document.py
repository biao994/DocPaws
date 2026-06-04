"""
文档 / 文件对象 / KB文件关联 / 切片 表（资产表族）
"""
from datetime import datetime
from uuid import uuid4

from docpaws.domain.datetime_utils import utc_now

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid4().hex


class Document(SQLModel, table=True):
    """文档表 - 支持上传文件或手动创建"""
    __table_args__ = (
        UniqueConstraint("kb_id", "title", "folder_path", name="unique_kb_id_title_folder_path"),
    )
    id: str = Field(default_factory=_uuid, primary_key=True)
    kb_id: str = Field(index=True)
    kb_file_id: str | None = Field(default=None, index=True)
    title: str = Field(max_length=200)
    content: str = Field(default="")
    status: str = Field(default="draft", description="draft/indexing/ready/failed")
    version: int = Field(default=1)
    folder_id: str | None = Field(default=None, index=True, foreign_key="kb_folder.id")
    folder_path: str | None = Field(default=None, index=True, max_length=200)
    indexed_content_hash: str | None = Field(default=None, index=True, description="当前激活索引对应的文件内容指纹")
    indexed_artifact_id: str | None = Field(
        default=None,
        index=True,
        foreign_key="indexartifact.id",
        description="当前激活索引产物 id",
    )
    indexed_at: datetime | None = Field(default=None)
    thumbnail_key: str | None = Field(default=None, index=True, description="S3 缩略图 object key")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class FileObject(SQLModel, table=True):
    """文件对象表 - 用于去重，相同内容只存一份"""
    id: str = Field(default_factory=_uuid, primary_key=True)
    storage_provider: str = Field(default="minio", description="存储提供方：local|minio|s3", index=True)
    object_key: str = Field(description="对象存储 key（或本地存储时的相对 key）", index=True)
    sha256: str = Field(index=True, unique=True)
    size_bytes: int = Field(description="文件大小(字节)")
    file_type: str = Field(description="文件类型")
    created_at: datetime = Field(default_factory=utc_now)


class KbFile(SQLModel, table=True):
    """知识库文件表 - 记录一次上传"""
    id: str = Field(default_factory=_uuid, primary_key=True)
    kb_id: str = Field(index=True)
    file_object_id: str = Field(index=True)
    original_filename: str = Field(max_length=200)
    uploaded_by: str = Field(index=True)
    status: str = Field(default="active", description="active/deleted")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    deleted_at: datetime | None = Field(default=None)


class Chunk(SQLModel, table=True):
    """切片表 - 引用可追溯"""
    id: str = Field(default_factory=_uuid, primary_key=True)
    document_id: str = Field(index=True)
    content: str = Field()
    page_no: int | None = Field(default=None)
    start_offset: int | None = Field(default=None)
    end_offset: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)
