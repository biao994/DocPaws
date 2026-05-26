"""
反馈路由
"""
from fastapi import APIRouter, Request, Depends
from sqlmodel import Session

from docpaws.api.deps import DependsSession, get_feedback_service, get_current_user
from docpaws.domain.models.user import User
from docpaws.api.response import success
from docpaws.api.schemas.feedback import FeedbackRequest
from docpaws.usecases.feedback_service import FeedbackService

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("/feedback")
def api_create_feedback(
    request: Request,
    req: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    svc: FeedbackService = Depends(get_feedback_service),
):
    data = svc.create_feedback(
        answer_id=req.answer_id,
        user_id=current_user.id,
        rating=req.rating,
        comment=req.comment,
    )

    return success(data=data, request_id=request.state.request_id)
