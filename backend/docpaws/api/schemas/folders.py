"""
文件夹 API DTO
"""
from datetime import datetime

from pydantic import BaseModel


class FolderCreateRequest(BaseModel):
    name: str
    parent_id: str | None = None


class FolderUpdateRequest(BaseModel):
    name: str


class FolderData(BaseModel):
    id: str
    kb_id: str
    parent_id: str | None
    name: str
    path: str | None
    created_at: datetime
    updated_at: datetime
