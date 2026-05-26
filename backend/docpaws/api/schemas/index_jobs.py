"""
索引任务 DTO
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class IndexJobData(BaseModel):
    id: str
    kb_id: str
    status: str
    progress: int
    error_message: str | None
    diff_summary: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
