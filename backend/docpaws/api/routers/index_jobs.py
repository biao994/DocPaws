"""
索引任务路由
"""
from fastapi import APIRouter, Request, Depends
from sqlmodel import Session

from docpaws.api.authz import require_document_readable, require_index_job_readable
from docpaws.api.deps import DependsSession, get_index_service, get_current_user
from docpaws.domain.models.user import User
from docpaws.api.response import success, get_status_code, ErrorCode
from docpaws.usecases.index_service import IndexService
from docpaws.errors import AppError

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/index-jobs/{job_id}")
def api_get_index_job(
    request: Request,
    job_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = DependsSession,
    svc: IndexService = Depends(get_index_service),
):
    require_index_job_readable(session, job_id, current_user.id)

    data = svc.get_job(job_id=job_id)
    if not data:
        raise AppError(
            error_code=ErrorCode.JOB_NOT_FOUND,
            message="index job not found",
            status_code=get_status_code(ErrorCode.JOB_NOT_FOUND),
            details={"job_id": job_id},
        )
    return success(data=data, request_id=request.state.request_id)


@router.get("/index-jobs/documents/{document_id}/index-job")
def api_get_document_index_job(
    request: Request,
    document_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = DependsSession,
    svc: IndexService = Depends(get_index_service),
):
    require_document_readable(session, document_id, current_user.id)

    data = svc.get_document_latest_job(document_id=document_id)
    if not data:
        raise AppError(
            error_code=ErrorCode.JOB_NOT_FOUND,
            message="index job not found",
            status_code=get_status_code(ErrorCode.JOB_NOT_FOUND),
            details={"document_id": document_id},
        )
    return success(data=data, request_id=request.state.request_id)
