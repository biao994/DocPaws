"""
知识库文件夹路由
"""
from fastapi import APIRouter, Depends, Query, Request

from docpaws.api.authz import require_kb_owned
from docpaws.api.deps import DependsSession, get_current_user, get_folder_service
from docpaws.api.response import success
from docpaws.api.schemas.folders import FolderCreateRequest, FolderUpdateRequest
from docpaws.domain.models.user import User
from docpaws.usecases.folder_service import FolderService
from sqlmodel import Session

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/knowledge-bases/{kb_id}/folders")
def api_list_folders(
    request: Request,
    kb_id: str,
    parent_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    session: Session = DependsSession,
    svc: FolderService = Depends(get_folder_service),
):
    require_kb_owned(session, kb_id, current_user.id)
    items = svc.list_folders(kb_id=kb_id, parent_id=parent_id)
    return success(data={"items": items}, request_id=request.state.request_id)


@router.post("/knowledge-bases/{kb_id}/folders")
def api_create_folder(
    request: Request,
    kb_id: str,
    req: FolderCreateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = DependsSession,
    svc: FolderService = Depends(get_folder_service),
):
    require_kb_owned(session, kb_id, current_user.id)
    data = svc.create_folder(kb_id=kb_id, name=req.name, parent_id=req.parent_id)
    return success(data=data, request_id=request.state.request_id)


@router.patch("/knowledge-bases/{kb_id}/folders/{folder_id}")
def api_rename_folder(
    request: Request,
    kb_id: str,
    folder_id: str,
    req: FolderUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = DependsSession,
    svc: FolderService = Depends(get_folder_service),
):
    require_kb_owned(session, kb_id, current_user.id)
    data = svc.rename_folder(folder_id=folder_id, name=req.name)
    return success(data=data, request_id=request.state.request_id)


@router.delete("/knowledge-bases/{kb_id}/folders/{folder_id}")
def api_delete_folder(
    request: Request,
    kb_id: str,
    folder_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = DependsSession,
    svc: FolderService = Depends(get_folder_service),
):
    require_kb_owned(session, kb_id, current_user.id)
    data = svc.delete_folder(folder_id=folder_id)
    return success(data=data, request_id=request.state.request_id)
