"""
反馈相关业务编排（用于保持路由薄）
"""

from sqlmodel import Session

from docpaws.domain.models.chat import Feedback
from docpaws.errors import AppError
from docpaws.api.response import ErrorCode, get_status_code


def _to_feedback_data(fb: Feedback) -> dict:
    from docpaws.api.schemas.feedback import FeedbackData

    return FeedbackData(
        id=fb.id,
        answer_id=fb.answer_id,
        rating=fb.rating,
        comment=fb.comment,
        created_at=fb.created_at,
    ).model_dump()

def _create_feedback_impl(
    session: Session,
    *,
    answer_id: str,
    user_id: str,
    rating: str,
    comment: str | None = None,
) -> Feedback:
    from docpaws.infra.repos.feedback_repo import get_answer_by_id
    from docpaws.infra.repos.conversation_repo import get_conversation_by_id

    answer = get_answer_by_id(session, answer_id)
    if not answer:
        raise AppError(
            error_code=ErrorCode.ANSWER_NOT_FOUND,
            message="答案不存在",
            status_code=get_status_code(ErrorCode.ANSWER_NOT_FOUND),
        )

    conv = get_conversation_by_id(session, answer.conversation_id)
    if not conv:
        raise AppError(
            error_code=ErrorCode.ANSWER_NOT_FOUND,
            message="答案不存在",
            status_code=get_status_code(ErrorCode.ANSWER_NOT_FOUND),
        )
    if conv.user_id != user_id:
        raise AppError(
            error_code=ErrorCode.FORBIDDEN,
            message="无权对该答案提交反馈",
            status_code=get_status_code(ErrorCode.FORBIDDEN),
        )

    if rating not in ("like", "dislike"):
        raise AppError(error_code=ErrorCode.VALIDATION_ERROR, message="rating 必须是 like 或 dislike", status_code=400)

    fb = Feedback(answer_id=answer_id, user_id=user_id, rating=rating, comment=comment)
    session.add(fb)
    session.commit()
    session.refresh(fb)
    return fb

class FeedbackService:
    def __init__(self, session: Session):
        self.session = session

    def create_feedback(
        self,
        *,
        answer_id: str,
        user_id: str,
        rating: str,
        comment: str | None = None,
    ) -> dict:
        fb = _create_feedback_impl(
            self.session,
            answer_id=answer_id,
            user_id=user_id,
            rating=rating,
            comment=comment,
        )
        return _to_feedback_data(fb)




