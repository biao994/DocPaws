"""
对话问答路由（SSE 流式响应）
"""
import json
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse

from docpaws.api.deps import get_chat_service, get_current_user
from docpaws.domain.models.user import User
from docpaws.api.response import success, ErrorCode, get_status_code, ERROR_CODE_TO_HINT
from docpaws.api.schemas.chat import ChatRequest
from docpaws.usecases.chat_service import ChatService
from docpaws.errors import AppError

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("/chat")
def api_chat(
    request: Request,
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    svc: ChatService = Depends(get_chat_service),
):
    """非流式问答（将流式输出聚合为一次性返回）"""
    svc.ensure_kb_and_index_ready(kb_id=req.kb_id, user_id=current_user.id)

    request_id = request.state.request_id

    uid = current_user.id

    async def _run() -> dict:
        chunks: list[str] = []
        final_message_id = ""
        final_conversation_id = req.conversation_id
        final_answer_id = ""
        citations = []
        async for payload in svc.stream_answer(
            kb_id=req.kb_id,
            question=req.question,
            conversation_id=req.conversation_id,
            request_id=request_id,
            user_id=uid,
            document_id=req.document_id,
            folder_id=req.folder_id,
            chat_mode=req.chat_mode,
        ):
            if payload.get("type") == "error":
                code = payload.get("code") or ErrorCode.INTERNAL_ERROR
                raise AppError(
                    error_code=str(code),
                    message=str(payload.get("content") or "处理失败"),
                    status_code=get_status_code(str(code)),
                    user_hint=ERROR_CODE_TO_HINT.get(str(code)),
                )
            if payload.get("type") == "answer_chunk":
                chunks.append(payload.get("content", ""))
                if payload.get("finished"):
                    final_message_id = payload.get("message_id", "") or ""
                    final_conversation_id = payload.get("conversation_id") or final_conversation_id
                    final_answer_id = payload.get("answer_id", "") or ""
                    citations = payload.get("citations", []) or []
                    break
        return {
            "conversation_id": final_conversation_id,
            "message_id": final_message_id,
            "answer_id": final_answer_id,
            "answer": "".join(chunks),
            "citations": citations,
        }

    import anyio

    data = anyio.run(_run)
    return success(data=data, request_id=request_id)


@router.post("/chat/stream")
def api_chat_stream(
    request: Request,
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    svc: ChatService = Depends(get_chat_service),
):
    """流式问答 (SSE)"""
    svc.ensure_kb_and_index_ready(kb_id=req.kb_id, user_id=current_user.id)
    request_id = request.state.request_id

    async def sse_generator():
        async for payload in svc.stream_answer(
            kb_id=req.kb_id,
            question=req.question,
            conversation_id=req.conversation_id,
            request_id=request_id,
            user_id=current_user.id,
            document_id=req.document_id,
            folder_id=req.folder_id,
            chat_mode=req.chat_mode,
        ):
            ptype = payload.pop("type", "")
            if ptype:
                payload["event"] = ptype
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(sse_generator(), media_type="text/event-stream")
