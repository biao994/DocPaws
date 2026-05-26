"""
对话检索范围：整库 / 文件夹 / 单文件
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from docpaws.api.response import ErrorCode
from docpaws.domain.models.chat import Conversation
from docpaws.domain.models.document import Document
from docpaws.errors import AppError
from docpaws.infra.repos.folder_repo import get_folder_by_id, list_documents_in_folder_tree

SCOPE_KB = "kb"
SCOPE_FOLDER = "folder"
SCOPE_FILE = "file"


def scope_from_request(*, document_id: str | None, folder_id: str | None) -> tuple[str, str | None]:
    if document_id:
        return SCOPE_FILE, document_id
    if folder_id:
        return SCOPE_FOLDER, folder_id
    return SCOPE_KB, None


def validate_scope(
    session: Session,
    *,
    kb_id: str,
    scope_type: str,
    scope_id: str | None,
) -> None:
    if scope_type == SCOPE_KB:
        return
    if scope_type == SCOPE_FILE:
        if not scope_id:
            raise AppError(
                error_code=ErrorCode.DOCUMENT_NOT_FOUND,
                message="文件范围缺少 document_id",
                status_code=400,
            )
        doc = session.get(Document, scope_id)
        if not doc or doc.kb_id != kb_id:
            raise AppError(
                error_code=ErrorCode.DOCUMENT_NOT_FOUND,
                message="文档不存在",
                status_code=404,
            )
        return
    if scope_type == SCOPE_FOLDER:
        if not scope_id:
            raise AppError(
                error_code=ErrorCode.KB_NOT_FOUND,
                message="文件夹范围缺少 folder_id",
                status_code=400,
            )
        folder = get_folder_by_id(session, scope_id)
        if not folder or folder.kb_id != kb_id:
            raise AppError(
                error_code=ErrorCode.KB_NOT_FOUND,
                message="文件夹不存在",
                status_code=404,
            )
        return
    raise AppError(
        error_code=ErrorCode.INTERNAL_ERROR,
        message=f"不支持的 scope_type: {scope_type}",
        status_code=400,
    )


def resolve_effective_scope(
    *,
    conversation: Conversation | None,
    document_id: str | None,
    folder_id: str | None,
) -> tuple[str, str | None]:
    """续聊用会话已存范围；新会话用本次请求。"""
    if conversation:
        st = getattr(conversation, "scope_type", None) or SCOPE_KB
        sid = getattr(conversation, "scope_id", None)
        return st, sid
    return scope_from_request(document_id=document_id, folder_id=folder_id)


def document_ids_for_scope(
    session: Session,
    *,
    kb_id: str,
    scope_type: str,
    scope_id: str | None,
) -> list[str] | None:
    """返回允许检索的 document_id 列表；整库返回 None。"""
    if scope_type == SCOPE_KB:
        return None
    if scope_type == SCOPE_FILE:
        return [scope_id] if scope_id else []
    if scope_type == SCOPE_FOLDER and scope_id:
        docs = list_documents_in_folder_tree(session, kb_id, scope_id)
        return [d.id for d in docs]
    return []


def build_faiss_filter(document_ids: list[str] | None) -> dict[str, Any] | Callable[[dict], bool] | None:
    if not document_ids:
        return None
    if len(document_ids) == 1:
        return {"document_id": document_ids[0]}
    allowed = set(document_ids)
    return lambda meta: meta.get("document_id") in allowed


def scope_cache_token(scope_type: str, scope_id: str | None) -> str:
    return f"{scope_type}:{scope_id or ''}"


def count_documents_in_scope(
    session: Session,
    *,
    kb_id: str,
    scope_type: str,
    scope_id: str | None,
) -> int:
    doc_ids = document_ids_for_scope(
        session, kb_id=kb_id, scope_type=scope_type, scope_id=scope_id
    )
    if doc_ids is None:
        return int(
            session.exec(
                select(func.count()).select_from(Document).where(Document.kb_id == kb_id)
            ).one()
        )
    return len(doc_ids)


def list_document_titles_in_scope(
    session: Session,
    *,
    kb_id: str,
    scope_type: str,
    scope_id: str | None,
    limit: int = 30,
) -> list[str]:
    doc_ids = document_ids_for_scope(
        session, kb_id=kb_id, scope_type=scope_type, scope_id=scope_id
    )
    if doc_ids is None:
        stmt = (
            select(Document)
            .where(Document.kb_id == kb_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
        )
        docs = list(session.exec(stmt).all())
    elif not doc_ids:
        return []
    else:
        stmt = select(Document).where(Document.id.in_(doc_ids)).limit(limit)
        docs = list(session.exec(stmt).all())
    return [d.title for d in docs if d.title]


def resolve_document_id_from_question(
    session: Session,
    *,
    kb_id: str,
    scope_type: str,
    scope_id: str | None,
    text: str,
) -> str | None:
    """
    从用户问题中识别明确提到的文档标题，返回对应 document_id。
    优先匹配更长标题，避免「2023_PDF3」误命中「2023_PDF2」。
    """
    query = (text or "").strip().lower()
    if not query:
        return None

    allowed_ids = document_ids_for_scope(
        session, kb_id=kb_id, scope_type=scope_type, scope_id=scope_id
    )
    if allowed_ids is not None and not allowed_ids:
        return None

    if allowed_ids is None:
        stmt = select(Document).where(Document.kb_id == kb_id)
    else:
        stmt = select(Document).where(Document.id.in_(allowed_ids))

    docs = list(session.exec(stmt).all())
    best: tuple[int, str] | None = None
    for doc in docs:
        title = (doc.title or "").strip()
        if len(title) < 2:
            continue
        if title.lower() in query:
            key = (len(title), doc.id)
            if best is None or key > best:
                best = key
    return best[1] if best else None


def document_title_for_id(session: Session, document_id: str | None) -> str | None:
    if not document_id:
        return None
    doc = session.get(Document, document_id)
    if not doc:
        return None
    title = (doc.title or "").strip()
    return title or None


def retrieval_filter_for_question(
    session: Session,
    *,
    kb_id: str,
    scope_type: str,
    scope_id: str | None,
    base_filter: dict[str, Any] | Callable[[dict], bool] | None,
    text: str,
) -> tuple[dict[str, Any] | Callable[[dict], bool] | None, str | None]:
    """
    在会话范围 filter 基础上，若问题点名某文档则收窄到该文件。
    返回 (filter, matched_document_id)。
    """
    if scope_type == SCOPE_FILE:
        return base_filter, scope_id

    doc_id = resolve_document_id_from_question(
        session,
        kb_id=kb_id,
        scope_type=scope_type,
        scope_id=scope_id,
        text=text,
    )
    if not doc_id:
        return base_filter, None
    return build_faiss_filter([doc_id]), doc_id


def retrieval_cache_scope_token(scope_token: str, document_id: str | None) -> str:
    if document_id:
        return f"{scope_token}@doc:{document_id}"
    return scope_token


def scope_prompt_label(
    session: Session,
    *,
    kb_id: str,
    scope_type: str,
    scope_id: str | None,
) -> str:
    if scope_type == SCOPE_KB:
        return "整个知识库"
    if scope_type == SCOPE_FILE and scope_id:
        doc = session.get(Document, scope_id)
        title = doc.title if doc and doc.kb_id == kb_id else scope_id
        return f"单个文件「{title}」"
    if scope_type == SCOPE_FOLDER and scope_id:
        folder = get_folder_by_id(session, scope_id)
        name = folder.name if folder and folder.kb_id == kb_id else scope_id
        return f"文件夹「{name}」（含子文件夹）"
    return "当前范围"
