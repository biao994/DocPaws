"""
对话检索范围：按 scope 查库（infra 实现）
"""
from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from docpaws.domain.models.document import Document
from docpaws.domain.services.chat_scope import (
    SCOPE_FOLDER,
    document_ids_from_scope,
    match_document_id_by_title,
)
from docpaws.infra.repos.document_repo import get_document_by_id
from docpaws.infra.repos.folder_repo import get_folder_by_id, list_documents_in_folder_tree


def fetch_document(session: Session, document_id: str) -> Document | None:
    return get_document_by_id(session, document_id)


def fetch_folder(session: Session, folder_id: str):
    return get_folder_by_id(session, folder_id)


def _folder_doc_ids(session: Session, kb_id: str, scope_type: str, scope_id: str | None) -> list[str]:
    if scope_type == SCOPE_FOLDER and scope_id:
        docs = list_documents_in_folder_tree(session, kb_id, scope_id)
        return [d.id for d in docs]
    return []


def document_ids_for_scope(
    session: Session,
    *,
    kb_id: str,
    scope_type: str,
    scope_id: str | None,
) -> list[str] | None:
    folder_doc_ids = _folder_doc_ids(session, kb_id, scope_type, scope_id)
    return document_ids_from_scope(scope_type, scope_id, folder_doc_ids=folder_doc_ids)


def count_documents_in_kb(session: Session, kb_id: str) -> int:
    return int(
        session.exec(
            select(func.count()).select_from(Document).where(Document.kb_id == kb_id)
        ).one()
    )


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
        return count_documents_in_kb(session, kb_id)
    return len(doc_ids)


def _list_documents_by_ids(session: Session, doc_ids: list[str], limit: int) -> list[Document]:
    stmt = select(Document).where(Document.id.in_(doc_ids)).limit(limit)
    return list(session.exec(stmt).all())


def list_documents_in_scope(
    session: Session,
    *,
    kb_id: str,
    scope_type: str,
    scope_id: str | None,
    allowed_ids: list[str] | None = None,
    limit: int | None = None,
) -> list[Document]:
    """列出 scope 内文档；allowed_ids 可传入已算好的 id 列表以省一次查询。"""
    doc_ids = allowed_ids
    if doc_ids is None:
        doc_ids = document_ids_for_scope(
            session, kb_id=kb_id, scope_type=scope_type, scope_id=scope_id
        )
    if doc_ids is not None and not doc_ids:
        return []
    if doc_ids is None:
        stmt = select(Document).where(Document.kb_id == kb_id)
        if limit is not None:
            stmt = stmt.order_by(Document.created_at.desc()).limit(limit)
        return list(session.exec(stmt).all())
    if limit is not None:
        return _list_documents_by_ids(session, doc_ids, limit)
    return _list_documents_by_ids(session, doc_ids, len(doc_ids) + 1)


def list_document_titles_in_scope(
    session: Session,
    *,
    kb_id: str,
    scope_type: str,
    scope_id: str | None,
    limit: int = 30,
) -> list[str]:
    docs = list_documents_in_scope(
        session,
        kb_id=kb_id,
        scope_type=scope_type,
        scope_id=scope_id,
        limit=limit,
    )
    return [d.title for d in docs if d.title]


def resolve_document_id_from_question(
    session: Session,
    *,
    kb_id: str,
    scope_type: str,
    scope_id: str | None,
    text: str,
) -> str | None:
    allowed_ids = document_ids_for_scope(
        session, kb_id=kb_id, scope_type=scope_type, scope_id=scope_id
    )
    if allowed_ids is not None and not allowed_ids:
        return None
    docs = list_documents_in_scope(
        session,
        kb_id=kb_id,
        scope_type=scope_type,
        scope_id=scope_id,
        allowed_ids=allowed_ids,
    )
    return match_document_id_by_title(text, docs)


def document_title_for_id(session: Session, document_id: str | None) -> str | None:
    if not document_id:
        return None
    doc = fetch_document(session, document_id)
    if not doc:
        return None
    title = (doc.title or "").strip()
    return title or None
