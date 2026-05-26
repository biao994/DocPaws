"""
知识库相关 Pydantic DTO（请求/响应）

只做 HTTP 层数据校验与序列化，不含 ORM 模型。
"""
from datetime import datetime
from pydantic import BaseModel


# ── 请求模型 ──

class KbCreateRequest(BaseModel):
    name: str
    description: str = ""

class KbUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None


# ── 响应模型 ──

class KbData(BaseModel):
    id: str
    name: str
    description: str
    owner_user_id: str
    created_at: datetime
    updated_at: datetime


class KbListData(BaseModel):
    items: list[KbData]
    page: int
    page_size: int
    total: int
