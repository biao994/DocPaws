"""
反馈相关 Repo（infra 实现）
"""

from sqlmodel import Session

from docpaws.domain.models.chat import Feedback


def create_feedback(
    session: Session,
    *,
    answer_id: str,
    user_id: str,
    rating: str,
    comment: str | None = None,
) -> Feedback:
    fb = Feedback(answer_id=answer_id, user_id=user_id, rating=rating, comment=comment)
    session.add(fb)
    session.commit()
    session.refresh(fb)
    return fb
