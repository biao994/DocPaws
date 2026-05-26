"""
知识库路由：只做 HTTP 适配（校验/调用 service/返回）
"""
from fastapi import APIRouter, Request, Depends

from sqlmodel import Session

from docpaws.api.authz import require_kb_owned
from docpaws.api.deps import get_kb_service, get_current_user, DependsSession
from docpaws.domain.models.user import User
from docpaws.api.response import success, get_status_code, ErrorCode
from docpaws.api.schemas.kb import KbCreateRequest, KbUpdateRequest
from docpaws.usecases.kb_service import KbService
from docpaws.errors import AppError

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("/knowledge-bases")
def api_create_kb(
    request: Request,
    req: KbCreateRequest,
    current_user: User = Depends(get_current_user),
    svc: KbService = Depends(get_kb_service),
):
    data = svc.create_kb(
        name=req.name,
        description=req.description,
        owner_user_id=current_user.id,
    )
    return success(data=data, request_id=request.state.request_id)


@router.get("/knowledge-bases")
def api_list_kbs(
    request: Request,
    current_user: User = Depends(get_current_user),
    page: int = 1,
    page_size: int = 20,
    svc: KbService = Depends(get_kb_service),
):
    data = svc.list_kbs(owner_user_id=current_user.id, page=page, page_size=page_size)
    return success(data=data, request_id=request.state.request_id)


@router.get("/knowledge-bases/{kb_id}")
def api_get_kb(
    request: Request,
    kb_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = DependsSession,
    svc: KbService = Depends(get_kb_service),
):
    require_kb_owned(session, kb_id, current_user.id)

    data = svc.get_kb_by_id(kb_id=kb_id)
    if not data:
        raise AppError(
            error_code=ErrorCode.KB_NOT_FOUND,
            message="knowledge base not found",
            status_code=get_status_code(ErrorCode.KB_NOT_FOUND),
        )
    return success(data=data, request_id=request.state.request_id)


@router.delete("/knowledge-bases/{kb_id}")
def api_delete_kb(
    request: Request,
    kb_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = DependsSession,
    svc: KbService = Depends(get_kb_service),
):
    require_kb_owned(session, kb_id, current_user.id)

    ok = svc.remove_kb(kb_id=kb_id)
    if not ok:
        raise AppError(
            error_code=ErrorCode.KB_NOT_FOUND,
            message="knowledge base not found",
            status_code=get_status_code(ErrorCode.KB_NOT_FOUND),
        )
    return success(data={"status": "deleted", "kb_id": kb_id}, request_id=request.state.request_id)


@router.patch("/knowledge-bases/{kb_id}")
def api_update_kb(
    request: Request,
    kb_id: str,
    req: KbUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = DependsSession,
    svc: KbService = Depends(get_kb_service),
):
    require_kb_owned(session, kb_id, current_user.id)
    data = svc.update_kb(kb_id=kb_id, name=req.name, description=req.description)
    if not data:
        raise AppError(
            error_code=ErrorCode.KB_NOT_FOUND,
            message="knowledge base not found",
            status_code=get_status_code(ErrorCode.KB_NOT_FOUND),
        )
    return success(data=data, request_id=request.state.request_id)
