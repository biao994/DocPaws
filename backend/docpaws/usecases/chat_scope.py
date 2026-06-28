"""
对话检索范围：薄兼容层（re-export + AppError 编排）

纯逻辑见 domain/services/chat_scope.py；查库见 infra/repos/scope_repo.py。
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlmodel import Session

from docpaws.api.response import ErrorCode
from docpaws.domain.services import chat_scope as scope_domain
from docpaws.errors import AppError
from docpaws.infra.repos import scope_repo

# 常量与纯函数 re-export（调用方可继续 from docpaws.usecases.chat_scope import ...）
SCOPE_KB = scope_domain.SCOPE_KB
SCOPE_FOLDER = scope_domain.SCOPE_FOLDER
SCOPE_FILE = scope_domain.SCOPE_FILE

scope_from_request = scope_domain.scope_from_request
resolve_effective_scope = scope_domain.resolve_effective_scope
build_faiss_filter = scope_domain.build_faiss_filter
scope_cache_token = scope_domain.scope_cache_token
retrieval_cache_scope_token = scope_domain.retrieval_cache_scope_token


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
        err = scope_domain.check_scope_file(
            scope_id, scope_repo.fetch_document(session, scope_id or ""), kb_id
        )
        if err == "missing_id":
            raise AppError(
                error_code=ErrorCode.DOCUMENT_NOT_FOUND,
                message="文件范围缺少 document_id",
                status_code=400,
            )
        if err == "not_found":
            raise AppError(
                error_code=ErrorCode.DOCUMENT_NOT_FOUND,
                message="文档不存在",
                status_code=404,
            )
        return
    if scope_type == SCOPE_FOLDER:
        err = scope_domain.check_scope_folder(
            scope_id, scope_repo.fetch_folder(session, scope_id or ""), kb_id
        )
        if err == "missing_id":
            raise AppError(
                error_code=ErrorCode.KB_NOT_FOUND,
                message="文件夹范围缺少 folder_id",
                status_code=400,
            )
        if err == "not_found":
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


def document_ids_for_scope(
    session: Session,
    *,
    kb_id: str,
    scope_type: str,
    scope_id: str | None,
) -> list[str] | None:
    return scope_repo.document_ids_for_scope(
        session, kb_id=kb_id, scope_type=scope_type, scope_id=scope_id
    )


def count_documents_in_scope(
    session: Session,
    *,
    kb_id: str,
    scope_type: str,
    scope_id: str | None,
) -> int:
    return scope_repo.count_documents_in_scope(
        session, kb_id=kb_id, scope_type=scope_type, scope_id=scope_id
    )


def list_document_titles_in_scope(
    session: Session,
    *,
    kb_id: str,
    scope_type: str,
    scope_id: str | None,
    limit: int = 30,
) -> list[str]:
    return scope_repo.list_document_titles_in_scope(
        session, kb_id=kb_id, scope_type=scope_type, scope_id=scope_id, limit=limit
    )


def resolve_document_id_from_question(
    session: Session,
    *,
    kb_id: str,
    scope_type: str,
    scope_id: str | None,
    text: str,
) -> str | None:
    return scope_repo.resolve_document_id_from_question(
        session,
        kb_id=kb_id,
        scope_type=scope_type,
        scope_id=scope_id,
        text=text,
    )


def document_title_for_id(session: Session, document_id: str | None) -> str | None:
    return scope_repo.document_title_for_id(session, document_id)


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


def scope_prompt_label(
    session: Session,
    *,
    kb_id: str,
    scope_type: str,
    scope_id: str | None,
) -> str:
    doc_title: str | None = None
    folder_name: str | None = None
    if scope_type == SCOPE_FILE and scope_id:
        doc = scope_repo.fetch_document(session, scope_id)
        if doc and doc.kb_id == kb_id:
            doc_title = doc.title
    elif scope_type == SCOPE_FOLDER and scope_id:
        folder = scope_repo.fetch_folder(session, scope_id)
        if folder and folder.kb_id == kb_id:
            folder_name = folder.name
    return scope_domain.format_scope_prompt_label(
        scope_type,
        scope_id,
        doc_title=doc_title,
        folder_name=folder_name,
    )
