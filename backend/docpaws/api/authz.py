"""
资源归属：区分「不存在」404 与 「存在但无权」403。
"""
from sqlmodel import Session

from docpaws.domain.models.document import Document
from docpaws.domain.models.index import IndexJob
from docpaws.domain.models.kb import KnowledgeBase
from docpaws.infra.repos.kb_repo import get_kb_by_id
from docpaws.errors import AppError
from docpaws.api.response import ErrorCode, get_status_code


def require_kb_owned(session: Session, kb_id: str, user_id: str) -> KnowledgeBase:
    kb = get_kb_by_id(session, kb_id)
    if not kb:
        raise AppError(
            error_code=ErrorCode.KB_NOT_FOUND,
            message="知识库不存在",
            status_code=get_status_code(ErrorCode.KB_NOT_FOUND),
        )
    if kb.owner_user_id != user_id:
        raise AppError(
            error_code=ErrorCode.FORBIDDEN,
            message="无权访问该知识库",
            status_code=get_status_code(ErrorCode.FORBIDDEN),
        )
    return kb


def require_document_readable(session: Session, document_id: str, user_id: str) -> Document:
    doc = session.get(Document, document_id)
    if not doc:
        raise AppError(
            error_code=ErrorCode.DOCUMENT_NOT_FOUND,
            message="文档不存在",
            status_code=get_status_code(ErrorCode.DOCUMENT_NOT_FOUND),
        )
    require_kb_owned(session, doc.kb_id, user_id)
    return doc


def require_index_job_readable(session: Session, job_id: str, user_id: str) -> IndexJob:
    job = session.get(IndexJob, job_id)
    if not job:
        raise AppError(
            error_code=ErrorCode.JOB_NOT_FOUND,
            message="index job not found",
            status_code=get_status_code(ErrorCode.JOB_NOT_FOUND),
            details={"job_id": job_id},
        )
    require_kb_owned(session, job.kb_id, user_id)
    return job
