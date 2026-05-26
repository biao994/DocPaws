"""
会话管理路由
"""
from fastapi import APIRouter, Request, Depends, Query

from docpaws.domain.models.user import User
from docpaws.api.deps import get_conversation_service, get_current_user
from docpaws.api.response import success
from docpaws.usecases.conversation_service import ConversationService

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/knowledge-bases/{kb_id}/conversations")
def api_list_conversations(
    request: Request,
    kb_id: str,
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    scope_type: str | None = Query(None, description="kb / folder / file"),
    scope_id: str | None = Query(None, description="folder_id 或 document_id；整库不传"),
    svc: ConversationService = Depends(get_conversation_service),
):
    items, total = svc.list_conversations(
        kb_id=kb_id,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    return success(data={
        "items": items,
        "page": page, "page_size": page_size, "total": total,
    }, request_id=request.state.request_id)


@router.get("/conversations/{conversation_id}")
def api_get_conversation(
    request: Request,
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    svc: ConversationService = Depends(get_conversation_service),
):
    data = svc.get_conversation(conversation_id=conversation_id, user_id=current_user.id)
    return success(data=data, request_id=request.state.request_id)


@router.get("/conversations")
def api_list_all_conversations(
    request: Request,
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: ConversationService = Depends(get_conversation_service),
):
    items, total = svc.list_all_conversations(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    return success(data={
        "items": items,
        "page": page, "page_size": page_size, "total": total,
    }, request_id=request.state.request_id)

@router.delete("/conversations/{conversation_id}")
def api_delete_conversation(
    request: Request,
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    svc: ConversationService = Depends(get_conversation_service),
):
    svc.delete_conversation(conversation_id=conversation_id, user_id=current_user.id)
    return success(data={"id": conversation_id, "deleted": True}, request_id=request.state.request_id)
