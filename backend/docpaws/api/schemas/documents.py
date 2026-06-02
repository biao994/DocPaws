"""
文档相关 Pydantic DTO
"""
from datetime import datetime
from pydantic import BaseModel


class DocumentData(BaseModel):
    id: str
    kb_id: str
    kb_file_id: str | None = None
    title: str
    status: str
    version: int
    folder_id: str | None = None
    folder_path: str | None
    created_at: datetime
    has_thumbnail: bool = False


class DocumentUpdateRequest(BaseModel):
    title: str


class UploadData(BaseModel):
    document_id: str
    job_id: str
    original_filename: str
    size_bytes: int
    sha256: str
    is_duplicate: bool
    is_replace: bool = False
    auto_renamed: bool = False
    should_enqueue: bool = True


class DocumentDeleteData(BaseModel):
    status: str
    document_id: str
    physical_file_deleted: bool
    job_id: str | None = None
    should_enqueue: bool = False


class BatchUploadItemData(BaseModel):
    document_id: str
    original_filename: str
    size_bytes: int
    sha256: str
    is_duplicate: bool
    auto_renamed: bool
    folder_path: str | None = None
    title: str


class BatchUploadData(BaseModel):
    kb_id: str
    job_id: str
    should_enqueue: bool = True
    total: int
    items: list[BatchUploadItemData]
