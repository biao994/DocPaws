"""
对话检索范围：纯领域逻辑
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from docpaws.domain.models.chat import Conversation
from docpaws.domain.models.document import Document
from docpaws.domain.models.folder import KbFolder

SCOPE_KB = "kb"
SCOPE_FOLDER = "folder"
SCOPE_FILE = "file"


def scope_from_request(*, document_id: str | None, folder_id: str | None) -> tuple[str, str | None]:
    if document_id:
        return SCOPE_FILE, document_id
    if folder_id:
        return SCOPE_FOLDER, folder_id
    return SCOPE_KB, None


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


def document_ids_from_scope(
    scope_type: str,
    scope_id: str | None,
    *,
    folder_doc_ids: list[str],
) -> list[str] | None:
    """返回允许检索的 document_id 列表；整库返回 None。"""
    if scope_type == SCOPE_KB:
        return None
    if scope_type == SCOPE_FILE:
        return [scope_id] if scope_id else []
    if scope_type == SCOPE_FOLDER:
        return folder_doc_ids
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


def retrieval_cache_scope_token(scope_token: str, document_id: str | None) -> str:
    if document_id:
        return f"{scope_token}@doc:{document_id}"
    return scope_token


def check_scope_file(
    scope_id: str | None,
    doc: Document | None,
    kb_id: str,
) -> str | None:
    """返回 'missing_id' | 'not_found' | None（合法）。"""
    if not scope_id:
        return "missing_id"
    if not doc or doc.kb_id != kb_id:
        return "not_found"
    return None


def check_scope_folder(
    scope_id: str | None,
    folder: KbFolder | None,
    kb_id: str,
) -> str | None:
    """返回 'missing_id' | 'not_found' | None（合法）。"""
    if not scope_id:
        return "missing_id"
    if not folder or folder.kb_id != kb_id:
        return "not_found"
    return None


def match_document_id_by_title(text: str, docs: list[Document]) -> str | None:
    """
    从用户问题中识别明确提到的文档标题，返回对应 document_id。
    优先匹配更长标题，避免「2023_PDF3」误命中「2023_PDF2」。
    """
    query = (text or "").strip().lower()
    if not query:
        return None

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


def format_scope_prompt_label(
    scope_type: str,
    scope_id: str | None,
    *,
    doc_title: str | None = None,
    folder_name: str | None = None,
) -> str:
    if scope_type == SCOPE_KB:
        return "整个知识库"
    if scope_type == SCOPE_FILE and scope_id:
        title = doc_title if doc_title else scope_id
        return f"单个文件「{title}」"
    if scope_type == SCOPE_FOLDER and scope_id:
        name = folder_name if folder_name else scope_id
        return f"文件夹「{name}」（含子文件夹）"
    return "当前范围"
