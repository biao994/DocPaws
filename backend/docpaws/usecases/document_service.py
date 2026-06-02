"""
文档上传 / 删除 业务编排

核心逻辑：文件落盘 -> 去重 -> 创建 Document/KbFile -> 合并为 KB 级 IndexJob -> 按需触发后台索引。
"""
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import UploadFile
from sqlmodel import Session

from docpaws.api.schemas.documents import DocumentData, DocumentDeleteData, UploadData
from docpaws.domain.models.document import Document, FileObject, KbFile
from docpaws.errors import AppError
from docpaws.infra.storage.local_fs import storage
from docpaws.infra.storage.s3_minio import delete_object, head_meta, head_object, upload_file
from docpaws.settings import settings


def normalize_folder_path(folder_path: Optional[str]) -> Optional[str]:
    """
    将用户输入的 folder_path 归一化为稳定表示：
    - None / "" / "/" -> None（根目录）
    - "\\" -> "/"
    - 去首尾 "/"
    - 去除空段（"a//b" -> "a/b"）
    - 禁止 "." / ".." 段，避免路径穿越与脏数据
    """
    if folder_path is None:
        return None
    p = folder_path.strip()
    if p in {"", "/"}:
        return None

    p = p.replace("\\", "/").strip("/")
    parts = [seg for seg in p.split("/") if seg]
    if not parts:
        return None
    if any(seg in {".", ".."} for seg in parts):
        raise AppError(
            error_code="VALIDATION_ERROR",
            message="非法 folder_path",
            status_code=400,
        )
    return "/".join(parts)


def _safe_filename(name: str) -> str:
    # 最小防御：只取 basename，且避免空名
    base = os.path.basename((name or "").replace("\\", "/")).strip() or "document.pdf"
    return base


def _build_object_key(*, user_id: str, kb_id: str, file_object_id: str, raw_filename: str) -> str:
    safe = _safe_filename(raw_filename)
    return f"u/{user_id}/kb/{kb_id}/doc/{file_object_id}/{safe}"


def _object_needs_reupload(*, object_key: str | None, size_bytes: int | None) -> bool:
    """
    去重复用 FileObject 时，判断是否需要用本次上传文件补传对象存储。

    触发条件：
    - object_key 为空
    - 对象不存在
    - DB size_bytes 为 0/空
    - 对象存在但 content_length 为 0（防止空 PDF 进入索引）
    """
    key = (object_key or "").strip()
    if not key:
        return True
    if not head_object(key):
        return True
    if (size_bytes or 0) <= 0:
        return True
    try:
        meta = head_meta(key)
        if int(meta.get("content_length") or 0) <= 0:
            return True
    except Exception:
        # 元信息读取失败：保守起见补传，避免坏对象继续传播
        return True
    return False


def _ensure_file_object_uploaded(
    *,
    session: Session,
    file_object: FileObject,
    temp_path: str,
    content_type: str,
    user_id: str,
    kb_id: str,
    raw_filename: str,
    size_bytes: int,
) -> None:
    """确保 FileObject 对应对象在存储中非空；必要时为其分配 object_key 并补传。"""
    if not _object_needs_reupload(object_key=file_object.object_key, size_bytes=file_object.size_bytes):
        return

    key = (file_object.object_key or "").strip()
    if not key:
        key = _build_object_key(
            user_id=user_id,
            kb_id=kb_id,
            file_object_id=file_object.id,
            raw_filename=raw_filename,
        )
        file_object.object_key = key

    upload_file(temp_path, key, content_type=content_type)
    file_object.size_bytes = size_bytes
    session.add(file_object)


def _folder_and_filename_from_relative(rel: str) -> tuple[Optional[str], str]:
    """relative_paths 单项：'a/b.pdf' -> (folder 'a', filename 'b.pdf')"""
    rel = rel.replace("\\", "/").strip()
    if not rel:
        raise AppError(error_code="VALIDATION_ERROR", message="relative_paths 含空项", status_code=400)
    name = os.path.basename(rel) or "document.pdf"
    parent = os.path.dirname(rel).replace("\\", "/").strip()
    if parent in {"", ".", "/"}:
        fp: Optional[str] = None
    else:
        fp = normalize_folder_path(parent)
    return fp, name


async def _ingest_one_pdf_create_no_commit(
    session: Session,
    file: UploadFile,
    raw_filename: str,
    kb_id: str,
    user_id: str,
    folder_path: Optional[str],
    on_conflict: str,
    folder_id: Optional[str] = None,
) -> dict:
    """
    在已有 session 内走 create/auto_rename 落库一条文档，不 commit、不创建 IndexJob。
    """
    from docpaws.usecases.folder_service import resolve_folder_for_document

    resolved_id, resolved_path = resolve_folder_for_document(
        session, kb_id, folder_id=folder_id, folder_path=folder_path
    )
    folder_id = resolved_id
    folder_path = resolved_path

    normalized = raw_filename if raw_filename.lower().endswith(".pdf") else f"{raw_filename}.pdf"
    auto_renamed = False
    if on_conflict == "auto_rename":
        for _ in range(100):
            doc_title = os.path.splitext(normalized)[0]
            from docpaws.infra.repos.document_repo import find_document

            if not find_document(session, kb_id, folder_path, doc_title, folder_id=folder_id):
                break
            base, ext = os.path.splitext(normalized)
            ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            normalized = f"{base}_{ts}{ext}"
            auto_renamed = True
        else:
            raise AppError(error_code="VALIDATION_ERROR", message="无法生成唯一文件名", status_code=400)

    if on_conflict == "create":
        from docpaws.infra.repos.document_repo import find_document

        existing = find_document(
            session, kb_id, folder_path, os.path.splitext(normalized)[0], folder_id=folder_id
        )
        if existing:
            raise AppError(
                error_code="NAME_CONFLICT",
                message="该位置已存在同名文档",
                status_code=409,
                details={
                    "existing_document_id": existing.id,
                    "existing_title": existing.title,
                    "incoming_filename": raw_filename,
                },
            )

    temp_path, sha256_hash, size = await storage.save_upload_to_temp_and_hash(file)
    is_duplicate = False

    try:
        from docpaws.infra.repos.document_repo import get_file_object_by_sha256

        existing_file = get_file_object_by_sha256(session, sha256_hash)

        if existing_file:
            file_object = existing_file
            is_duplicate = True

            if _object_needs_reupload(object_key=existing_file.object_key, size_bytes=existing_file.size_bytes):
                _ensure_file_object_uploaded(
                    session=session,
                    file_object=existing_file,
                    temp_path=temp_path,
                    content_type=file.content_type or "application/pdf",
                    user_id=user_id,
                    kb_id=kb_id,
                    raw_filename=raw_filename,
                    size_bytes=size,
                )
                temp_path = ""
        else:
            file_object = FileObject(
                id=uuid.uuid4().hex,
                storage_provider="minio",
                object_key="",
                sha256=sha256_hash,
                size_bytes=size,
                file_type="pdf",
            )
            object_key = _build_object_key(
                user_id=user_id,
                kb_id=kb_id,
                file_object_id=file_object.id,
                raw_filename=raw_filename,
            )
            upload_file(temp_path, object_key, content_type=file.content_type or "application/pdf")
            file_object.object_key = object_key
            temp_path = ""
            session.add(file_object)

        kb_file = KbFile(
            kb_id=kb_id,
            file_object_id=file_object.id,
            original_filename=raw_filename,
            uploaded_by=user_id,
            status="active",
        )
        session.add(kb_file)

        document = Document(
            kb_id=kb_id,
            kb_file_id=kb_file.id,
            title=os.path.splitext(normalized)[0],
            status="draft",
            version=1,
            folder_id=folder_id,
            folder_path=folder_path,
        )
        session.add(document)
        session.flush()

        return {
            "document_id": document.id,
            "original_filename": raw_filename,
            "size_bytes": size,
            "sha256": sha256_hash,
            "is_duplicate": is_duplicate,
            "auto_renamed": auto_renamed,
            "folder_id": folder_id,
            "folder_path": folder_path,
            "title": document.title,
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


async def commit_documents_batch(
    session: Session,
    *,
    kb_id: str,
    user_id: str,
    entries: list[tuple[UploadFile, Optional[str], str]],
    on_conflict: str = "create",
    idempotency_key: Optional[str] = None,
    folder_id: Optional[str] = None,
) -> dict:
    """
    批量上传 PDF：同一事务内写入多条 Document，最后只创建/复用一条 KB 级 IndexJob 并 commit。
    entries: (UploadFile, folder_path 已归一化, raw_filename 展示名)
    """
    batch_max = 100
    if not entries:
        raise AppError(error_code="VALIDATION_ERROR", message="至少上传一个 PDF 文件", status_code=400)
    if len(entries) > batch_max:
        raise AppError(
            error_code="VALIDATION_ERROR",
            message=f"单次最多上传 {batch_max} 个文件",
            status_code=400,
        )
    if on_conflict not in {"create", "auto_rename"}:
        raise AppError(
            error_code="VALIDATION_ERROR",
            message="批量上传仅支持 on_conflict=create 或 auto_rename",
            status_code=400,
        )

    items: list[dict] = []
    try:
        for file, fp, raw_fn in entries:
            row = await _ingest_one_pdf_create_no_commit(
                session, file, raw_fn, kb_id, user_id, fp, on_conflict, folder_id=folder_id
            )
            items.append(row)

        from docpaws.infra.repos.index_repo import ensure_kb_index_job

        job_id, should_enqueue = ensure_kb_index_job(session, kb_id, idempotency_key=idempotency_key)
        session.commit()
    except AppError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise

    return {
        "kb_id": kb_id,
        "job_id": job_id,
        "should_enqueue": should_enqueue,
        "items": items,
        "total": len(items),
    }


async def upload_document(
    session: Session,
    file: UploadFile,
    raw_filename: str,
    kb_id: str,
    user_id: str,
    folder_path: Optional[str] = None,
    folder_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    on_conflict: str = "create",
    replace_document_id: Optional[str] = None,
) -> dict:
    """
    上传文档主流程（返回 UploadData）

    由 router 调用，router 负责参数校验与 HTTP 异常。
    """
    from docpaws.usecases.folder_service import resolve_folder_for_document

    normalized = raw_filename if raw_filename.lower().endswith(".pdf") else f"{raw_filename}.pdf"
    resolved_id, resolved_path = resolve_folder_for_document(
        session, kb_id, folder_id=folder_id, folder_path=folder_path
    )
    folder_id = resolved_id
    folder_path = resolved_path

    auto_renamed = False
    if on_conflict == "auto_rename":
        for _ in range(100):
            doc_title = os.path.splitext(normalized)[0]
            from docpaws.infra.repos.document_repo import find_document

            if not find_document(session, kb_id, folder_path, doc_title, folder_id=folder_id):
                break
            base, ext = os.path.splitext(normalized)
            ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            normalized = f"{base}_{ts}{ext}"
            auto_renamed = True
        else:
            raise AppError(error_code="VALIDATION_ERROR", message="无法生成唯一文件名", status_code=400)

    if on_conflict == "create":
        from docpaws.infra.repos.document_repo import find_document

        existing = find_document(
            session, kb_id, folder_path, os.path.splitext(normalized)[0], folder_id=folder_id
        )
        if existing:
            raise AppError(
                error_code="NAME_CONFLICT",
                message="该位置已存在同名文档",
                status_code=409,
                details={
                    "existing_document_id": existing.id,
                    "existing_title": existing.title,
                    "incoming_filename": raw_filename,
                },
            )

    temp_path, sha256_hash, size = await storage.save_upload_to_temp_and_hash(file)
    is_duplicate = False

    try:
        from docpaws.infra.repos.document_repo import get_file_object_by_sha256

        existing_file = get_file_object_by_sha256(session, sha256_hash)

        if existing_file:
            # 复用 FileObject（去重）
            file_object = existing_file
            is_duplicate = True

            if _object_needs_reupload(object_key=existing_file.object_key, size_bytes=existing_file.size_bytes):
                _ensure_file_object_uploaded(
                    session=session,
                    file_object=existing_file,
                    temp_path=temp_path,
                    content_type=file.content_type or "application/pdf",
                    user_id=user_id,
                    kb_id=kb_id,
                    raw_filename=raw_filename,
                    size_bytes=size,
                )
                temp_path = ""
        else:
            file_object = FileObject(
                id=uuid.uuid4().hex,
                storage_provider="minio",
                object_key="",
                sha256=sha256_hash,
                size_bytes=size,
                file_type="pdf",
            )
            object_key = _build_object_key(
                user_id=user_id,
                kb_id=kb_id,
                file_object_id=file_object.id,
                raw_filename=raw_filename,
            )
            upload_file(temp_path, object_key, content_type=file.content_type or "application/pdf")
            file_object.object_key = object_key
            temp_path = ""
            session.add(file_object)

        if on_conflict == "replace":
            return _handle_replace(
                session,
                kb_id,
                replace_document_id or "",
                os.path.splitext(normalized)[0],
                file_object,
                normalized,
                size,
                sha256_hash,
                idempotency_key,
                auto_renamed,
            )

        kb_file = KbFile(
            kb_id=kb_id,
            file_object_id=file_object.id,
            original_filename=raw_filename,
            uploaded_by=user_id,
            status="active",
        )
        session.add(kb_file)

        document = Document(
            kb_id=kb_id,
            kb_file_id=kb_file.id,
            title=os.path.splitext(normalized)[0],
            status="draft",
            version=1,
            folder_id=folder_id,
            folder_path=folder_path,
        )
        session.add(document)

        if idempotency_key:
            from docpaws.infra.repos.index_repo import get_index_job_by_idempotency_key

            existing_job = get_index_job_by_idempotency_key(session, idempotency_key)
            if existing_job:
                session.rollback()
                return UploadData(
                    document_id=document.id,
                    job_id=existing_job.id,
                    original_filename=raw_filename,
                    size_bytes=size,
                    sha256=sha256_hash,
                    is_duplicate=is_duplicate,
                    should_enqueue=False,
                ).model_dump()

        from docpaws.infra.repos.index_repo import ensure_kb_index_job

        job_id, should_enqueue = ensure_kb_index_job(session, kb_id, idempotency_key=idempotency_key)
        session.commit()
        session.refresh(document)

        return UploadData(
            document_id=document.id,
            job_id=job_id,
            original_filename=raw_filename,
            size_bytes=size,
            sha256=sha256_hash,
            is_duplicate=is_duplicate,
            is_replace=False,
            auto_renamed=auto_renamed,
            should_enqueue=should_enqueue,
        ).model_dump()
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def delete_document(session: Session, document_id: str) -> dict:
    """删除文档及其级联数据；删除后入队 KB 级索引重建（FAISS 需整库对齐）。"""
    from docpaws.infra.repos.document_repo import delete_document_cascade
    from docpaws.infra.repos.index_repo import ensure_kb_index_job

    doc = session.get(Document, document_id)
    if not doc:
        return DocumentDeleteData(
            status="deleted",
            document_id=document_id,
            physical_file_deleted=False,
            job_id=None,
            should_enqueue=False,
        ).model_dump()

    kb_id = doc.kb_id
    object_key_to_remove, thumbnail_key_to_remove = delete_document_cascade(session, document_id)
    job_id, should_enqueue = ensure_kb_index_job(session, kb_id, idempotency_key=None)
    session.commit()

    physical_deleted = False
    if object_key_to_remove:
        try:
            delete_object(object_key_to_remove)
            physical_deleted = True
        except Exception:
            pass
    if thumbnail_key_to_remove:
        try:
            delete_object(thumbnail_key_to_remove)
        except Exception:
            pass

    return DocumentDeleteData(
        status="deleted",
        document_id=document_id,
        physical_file_deleted=physical_deleted,
        job_id=job_id,
        should_enqueue=should_enqueue,
    ).model_dump()


def _handle_replace(
    session: Session,
    kb_id: str,
    rid: str,
    doc_title: str,
    file_object: FileObject,
    normalized_filename: str,
    size: int,
    sha256: str,
    idempotency_key: Optional[str],
    auto_renamed: bool,
) -> dict:
    """替换模式处理逻辑"""
    from docpaws.infra.repos.document_repo import unlink_file_object_if_unused

    document = session.get(Document, rid)
    if not document or document.kb_id != kb_id:
        raise AppError(error_code="DOCUMENT_NOT_FOUND", message="文档不存在或已被删除", status_code=404)
    if not document.kb_file_id:
        raise AppError(error_code="VALIDATION_ERROR", message="该文档无文件记录，无法替换上传", status_code=400)

    kb_file = session.get(KbFile, document.kb_file_id)
    if not kb_file:
        raise AppError(error_code="VALIDATION_ERROR", message="文件记录不存在", status_code=400)

    old_fo_id = kb_file.file_object_id

    # 替换为同一 FileObject（内容完全相同、去重命中）：不删 chunk、不降级 draft，避免无索引进队时长期停在 draft
    if file_object.id == old_fo_id:
        if normalized_filename != (kb_file.original_filename or ""):
            kb_file.original_filename = normalized_filename
            kb_file.updated_at = datetime.utcnow()
            session.add(kb_file)
        from docpaws.infra.repos.index_repo import ensure_kb_index_job, get_latest_index_job_for_kb

        latest = get_latest_index_job_for_kb(session, kb_id)
        if latest:
            job_id, should_enqueue = latest.id, False
        else:
            job_id, should_enqueue = ensure_kb_index_job(session, kb_id, idempotency_key=None)
        session.commit()
        session.refresh(document)
        return UploadData(
            document_id=document.id,
            job_id=job_id,
            original_filename=normalized_filename,
            size_bytes=size,
            sha256=sha256,
            is_duplicate=True,
            is_replace=True,
            auto_renamed=auto_renamed,
            should_enqueue=should_enqueue,
        ).model_dump()

    from docpaws.infra.repos.document_repo import delete_chunks_by_document_id

    delete_chunks_by_document_id(session, document.id)

    kb_file.file_object_id = file_object.id
    kb_file.original_filename = normalized_filename
    kb_file.updated_at = datetime.utcnow()
    session.add(kb_file)

    physical_drop = unlink_file_object_if_unused(session, old_fo_id)

    document.version += 1
    document.status = "draft"
    document.updated_at = datetime.now()
    session.add(document)

    job_key = idempotency_key or f"{document.id}:v{document.version}"
    from docpaws.infra.repos.index_repo import get_index_job_by_idempotency_key

    existing_job = get_index_job_by_idempotency_key(session, job_key)
    if existing_job:
        session.rollback()
        return UploadData(
            document_id=document.id,
            job_id=existing_job.id,
            original_filename=normalized_filename,
            size_bytes=size,
            sha256=sha256,
            is_duplicate=True,
            is_replace=True,
            auto_renamed=auto_renamed,
            should_enqueue=False,
        ).model_dump()

    from docpaws.infra.repos.index_repo import ensure_kb_index_job

    job_id, should_enqueue = ensure_kb_index_job(session, kb_id, idempotency_key=job_key)
    session.commit()
    session.refresh(document)

    if physical_drop:
        try:
            delete_object(physical_drop)
        except Exception:
            pass

    return UploadData(
        document_id=document.id,
        job_id=job_id,
        original_filename=normalized_filename,
        size_bytes=size,
        sha256=sha256,
        is_duplicate=False,
        is_replace=True,
        auto_renamed=auto_renamed,
        should_enqueue=should_enqueue,
    ).model_dump()


def _to_doc_data(doc: Document) -> dict:
    return DocumentData(
        id=doc.id,
        kb_id=doc.kb_id,
        kb_file_id=doc.kb_file_id,
        title=doc.title,
        status=doc.status,
        version=doc.version,
        folder_id=doc.folder_id,
        folder_path=doc.folder_path,
        created_at=doc.created_at,
        has_thumbnail=bool((doc.thumbnail_key or "").strip()),
    ).model_dump()


def update_document_title(session: Session, *, document_id: str, title: str) -> dict:
    from docpaws.infra.repos.document_repo import find_document, get_document_by_id

    clean = (title or "").strip()
    if not clean:
        raise AppError(error_code="VALIDATION_ERROR", message="文档名称不能为空", status_code=400)
    if "/" in clean or "\\" in clean:
        raise AppError(error_code="VALIDATION_ERROR", message='文档名称不能包含 "/"', status_code=400)

    doc = get_document_by_id(session, document_id)
    if not doc:
        raise AppError(error_code="DOCUMENT_NOT_FOUND", message="文档不存在或已被删除", status_code=404)

    base_title = os.path.splitext(clean)[0] if clean.lower().endswith(".pdf") else clean
    conflict = find_document(
        session,
        doc.kb_id,
        doc.folder_path,
        base_title,
        folder_id=doc.folder_id,
    )
    if conflict and conflict.id != doc.id:
        raise AppError(
            error_code="NAME_CONFLICT",
            message="该位置已存在同名文档",
            status_code=409,
            details={"existing_document_id": conflict.id},
        )

    doc.title = base_title
    doc.updated_at = datetime.utcnow()
    if doc.kb_file_id:
        kb_file = session.get(KbFile, doc.kb_file_id)
        if kb_file:
            ext = ".pdf"
            if kb_file.original_filename and "." in kb_file.original_filename:
                ext = os.path.splitext(kb_file.original_filename)[1] or ".pdf"
            kb_file.original_filename = f"{base_title}{ext}"
            kb_file.updated_at = datetime.utcnow()
            session.add(kb_file)
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return _to_doc_data(doc)


def build_batch_upload_entries(
    files: list[UploadFile],
    folder_path: Optional[str],
    relative_paths: Optional[list[str]],
) -> list[tuple[UploadFile, Optional[str], str]]:
    """构造 (file, folder_path, raw_filename) 列表并校验 PDF / 路径数量。"""
    if not files:
        raise AppError(error_code="VALIDATION_ERROR", message="至少上传一个 PDF 文件", status_code=400)
    if relative_paths is not None and len(relative_paths) != len(files):
        raise AppError(
            error_code="VALIDATION_ERROR",
            message="relative_paths 数组长度必须与文件数量一致",
            status_code=400,
        )
    base_fp = normalize_folder_path(folder_path)
    entries: list[tuple[UploadFile, Optional[str], str]] = []
    for i, file in enumerate(files):
        raw_stripped = (file.filename or "").strip()
        if relative_paths:
            fp_i, raw_fn = _folder_and_filename_from_relative(relative_paths[i])
        else:
            fp_i, raw_fn = base_fp, raw_stripped
        if not raw_fn:
            raise AppError(error_code="VALIDATION_ERROR", message="文件名不能为空", status_code=400)
        is_pdf = raw_fn.lower().endswith(".pdf") or (file.content_type or "").lower() in {
            "application/pdf",
            "application/x-pdf",
        }
        if not is_pdf:
            raise AppError(error_code="VALIDATION_ERROR", message="仅支持 PDF 文件", status_code=400)
        entries.append((file, fp_i, raw_fn if relative_paths else raw_stripped))
    return entries


class DocumentService:
    def __init__(self, session: Session):
        self.session = session

    def list_documents(
        self,
        *,
        kb_id: str,
        status_filter: str | None = None,
        page: int = 1,
        page_size: int = 20,
        folder_path_filter: str | None = None,
        folder_id_filter: str | None = None,
    ) -> tuple[list[dict], int]:
        from docpaws.infra.repos.kb_repo import get_kb_by_id
        from docpaws.infra.repos.document_repo import list_documents as _list_docs

        if not get_kb_by_id(self.session, kb_id):
            raise AppError(error_code="KB_NOT_FOUND", message="知识库不存在", status_code=404)

        folder_path_filter = normalize_folder_path(folder_path_filter)
        items, total = _list_docs(
            self.session,
            kb_id,
            status_filter,
            page,
            page_size,
            folder_path_filter=folder_path_filter,
            folder_id_filter=folder_id_filter,
        )
        return ([_to_doc_data(d) for d in items], total)

    def update_document(self, *, document_id: str, title: str) -> dict:
        return update_document_title(self.session, document_id=document_id, title=title)

    def get_document(self, *, document_id: str) -> dict:
        from docpaws.infra.repos.document_repo import get_document_by_id

        doc = get_document_by_id(self.session, document_id)
        if not doc:
            raise AppError(error_code="DOCUMENT_NOT_FOUND", message="文档不存在或已被删除", status_code=404)
        return _to_doc_data(doc)

    def get_document_file(self, *, document_id: str) -> tuple[str, str]:
        """
        获取文档原始文件路径（用于 PDF 预览/下载）。

        Returns:
            (object_key, filename)
        """
        from docpaws.infra.repos.document_repo import get_document_by_id

        doc = get_document_by_id(self.session, document_id)
        if not doc:
            raise AppError(
                error_code="DOCUMENT_NOT_FOUND",
                message="文档不存在或已被删除",
                status_code=404,
            )

        if not doc.kb_file_id:
            raise AppError(
                error_code="FILE_NOT_FOUND",
                message="文件记录不存在",
                status_code=404,
            )

        kb_file = self.session.get(KbFile, doc.kb_file_id)
        if not kb_file or not kb_file.file_object_id:
            raise AppError(
                error_code="FILE_NOT_FOUND",
                message="文件记录不存在",
                status_code=404,
            )

        file_obj = self.session.get(FileObject, kb_file.file_object_id)
        if not file_obj or not file_obj.object_key:
            raise AppError(
                error_code="FILE_NOT_FOUND",
                message="文件不存在",
                status_code=404,
            )

        filename = doc.title or kb_file.original_filename or "document.pdf"
        if not filename.lower().endswith(".pdf"):
            filename = f"{filename}.pdf"
        return file_obj.object_key, filename

    def get_document_thumbnail(self, *, document_id: str) -> str:
        """返回缩略图 S3 object key；不存在时抛 AppError。"""
        from docpaws.infra.repos.document_repo import get_document_by_id

        doc = get_document_by_id(self.session, document_id)
        if not doc:
            raise AppError(
                error_code="DOCUMENT_NOT_FOUND",
                message="文档不存在或已被删除",
                status_code=404,
            )
        key = (doc.thumbnail_key or "").strip()
        if not key:
            raise AppError(
                error_code="FILE_NOT_FOUND",
                message="缩略图尚未生成",
                status_code=404,
                details={"document_id": document_id},
            )
        return key

    def delete_document(self, *, document_id: str) -> dict:
        return delete_document(self.session, document_id)

    async def upload_documents_batch(
        self,
        *,
        files: list[UploadFile],
        kb_id: str,
        user_id: str,
        folder_path: Optional[str] = None,
        folder_id: Optional[str] = None,
        relative_paths: Optional[list[str]] = None,
        on_conflict: str = "create",
        idempotency_key: Optional[str] = None,
    ) -> dict:
        entries = build_batch_upload_entries(files, folder_path, relative_paths)
        batch_folder_id = folder_id if not relative_paths else None
        return await commit_documents_batch(
            self.session,
            kb_id=kb_id,
            user_id=user_id,
            entries=entries,
            on_conflict=on_conflict,
            idempotency_key=idempotency_key,
            folder_id=batch_folder_id,
        )

    async def upload_document(
        self,
        *,
        file: UploadFile,
        raw_filename: str,
        kb_id: str,
        user_id: str,
        folder_path: Optional[str] = None,
        folder_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        on_conflict: str = "create",
        replace_document_id: Optional[str] = None,
    ) -> dict:
        return await upload_document(
            session=self.session,
            file=file,
            raw_filename=raw_filename,
            kb_id=kb_id,
            user_id=user_id,
            folder_path=folder_path,
            folder_id=folder_id,
            idempotency_key=idempotency_key,
            on_conflict=on_conflict,
            replace_document_id=replace_document_id,
        )
