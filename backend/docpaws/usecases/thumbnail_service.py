"""
文档缩略图：渲染首页 WebP → 上传 S3 → 写入 documents.thumbnail_key
"""
from __future__ import annotations

import logging
import os

from sqlmodel import Session

from docpaws.domain.models.document import Document
from docpaws.infra.parsers.pdf_thumbnail import render_first_page_webp
from docpaws.infra.repos.document_repo import resolve_document_file
from docpaws.infra.storage.s3_minio import delete_object, download_to_temp, upload_bytes
from docpaws.settings import settings

logger = logging.getLogger(__name__)

THUMBNAIL_CACHE_CONTROL = "public, max-age=86400, immutable"


def thumbnail_object_key(document_id: str) -> str:
    return f"thumbs/{document_id}.webp"


def generate_document_thumbnail(session: Session, document_id: str, *, pdf_path: str | None = None) -> str | None:
    """
    为文档生成缩略图并更新 thumbnail_key。

    pdf_path 可选：索引任务已下载 PDF 时可复用本地路径，避免重复下载。
    失败时记录日志并返回 None，不抛出异常（索引主流程不应被缩略图阻断）。
    """
    doc = session.get(Document, document_id)
    if not doc:
        return None

    temp_path = pdf_path
    owned_temp = False
    try:
        if not temp_path:
            object_key, _ = resolve_document_file(session, document_id)
            temp_path = download_to_temp(object_key)
            owned_temp = True

        webp_bytes = render_first_page_webp(temp_path, max_width=settings.THUMBNAIL_MAX_WIDTH)
        key = thumbnail_object_key(document_id)
        upload_bytes(webp_bytes, key, content_type="image/webp")

        old_key = (doc.thumbnail_key or "").strip()
        doc.thumbnail_key = key
        session.add(doc)
        session.commit()

        if old_key and old_key != key:
            try:
                delete_object(old_key)
            except Exception:
                logger.warning("failed to delete old thumbnail %s", old_key, exc_info=True)

        return key
    except Exception:
        logger.warning("thumbnail generation failed for document %s", document_id, exc_info=True)
        session.rollback()
        return None
    finally:
        if owned_temp and temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
