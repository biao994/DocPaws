"""
引用构建 / 回放 hydrate（chat 与 conversation 共用，避免互调）。
"""
import json

from sqlmodel import Session

from docpaws.infra.repos.document_repo import get_chunk_by_id, get_document_by_id


def get_citations_from_docs(docs, session: Session) -> list[dict]:
    """从检索结果构建引用信息"""
    citations = []
    for doc in docs:
        chunk_id = doc.metadata.get("chunk_id")
        document_id = doc.metadata.get("document_id")
        chunk = get_chunk_by_id(session, chunk_id) if chunk_id else None

        source_name = doc.metadata.get("source", "")
        if document_id and not source_name:
            db_doc = get_document_by_id(session, document_id)
            if db_doc:
                source_name = db_doc.title

        snippet = doc.page_content[:200] + ("..." if len(doc.page_content) > 200 else "")

        citations.append(
            {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "source": source_name,
                "page_no": chunk.page_no if chunk else doc.metadata.get("page"),
                "snippet": snippet,
            }
        )
    return citations


def hydrate_citations_from_stored(session: Session, stored) -> list[dict]:
    """从 Answer.citations 还原完整引用（兼容仅存 chunk_id 的旧数据）。"""
    if not stored:
        return []
    if isinstance(stored, str):
        try:
            stored = json.loads(stored)
        except (json.JSONDecodeError, TypeError):
            return []
    if not isinstance(stored, list):
        return []

    out: list[dict] = []
    for item in stored:
        if not isinstance(item, dict):
            continue
        chunk_id = item.get("chunk_id")
        if not chunk_id:
            continue
        if item.get("snippet"):
            out.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": item.get("document_id"),
                    "page_no": item.get("page_no"),
                    "snippet": item["snippet"],
                    "source": item.get("source"),
                }
            )
            continue
        chunk = get_chunk_by_id(session, chunk_id)
        if not chunk:
            continue
        document_id = chunk.document_id
        source_name = (item.get("source") or "").strip()
        if document_id and not source_name:
            db_doc = get_document_by_id(session, document_id)
            if db_doc:
                source_name = (db_doc.title or "").strip()
        content = chunk.content or ""
        snippet = content[:200] + ("..." if len(content) > 200 else "")
        out.append(
            {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "page_no": chunk.page_no,
                "snippet": snippet,
                "source": source_name or None,
            }
        )
    return out
