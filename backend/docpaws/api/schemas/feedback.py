"""
反馈 DTO
"""
from datetime import datetime
from pydantic import BaseModel


class FeedbackRequest(BaseModel):
    answer_id: str
    rating: str  # like/dislike
    comment: str | None = None


class FeedbackData(BaseModel):
    id: str
    answer_id: str
    rating: str
    comment: str | None
    created_at: datetime
