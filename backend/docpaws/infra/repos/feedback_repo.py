"""
反馈相关 Repo（infra 实现）
"""

from sqlmodel import Session

from docpaws.domain.models.index import Answer


def get_answer_by_id(session: Session, answer_id: str) -> Answer | None:
    return session.get(Answer, answer_id)

