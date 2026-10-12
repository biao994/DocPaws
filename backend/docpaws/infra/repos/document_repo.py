"""
文档 Repo（infra 实现）：所有文档/文件对象/KbFile/Chunk 查询与持久化细节
"""

import uuid

from sqlalchemy import func
from sqlmodel import Session, select

from docpaws.domain.datetime_utils import utc_now
from docpaws.domain.models.document import Document, FileObject, KbFile, Chunk


def get_document_by_id(session: Session, doc_id: str) -> Document | None:
    return session.get(Document, doc_id)


def get_chunk_by_id(session: Session, chunk_id: str) -> Chunk | None:
    return session.get(Chunk, chunk_id)


def get_kb_file_by_id(session: Session, kb_file_id: str) -> KbFile | None:
    return session.get(KbFile, kb_file_id)


def get_file_object_by_id(session: Session, file_object_id: str) -> FileObject | None:
    return session.get(FileObject, file_object_id)


def build_file_object(
    *,
    sha256: str,
    size_bytes: int,
    object_key: str = "",
    file_type: str = "pdf",
    storage_provider: str = "minio",
    file_object_id: str | None = None,
) -> FileObject:
    """构造 FileObject，不写 session（便于先上传对象存储再落库）。"""
    return FileObject(
        id=file_object_id or uuid.uuid4().hex,
        storage_provider=storage_provider,
        object_key=object_key,
        sha256=sha256,
        size_bytes=size_bytes,
        file_type=file_type,
    )


def create_file_object(
    session: Session,
    *,
    sha256: str,
    size_bytes: int,
    object_key: str = "",
    file_type: str = "pdf",
    storage_provider: str = "minio",
    file_object_id: str | None = None,
) -> FileObject:
    fo = build_file_object(
        sha256=sha256,
        size_bytes=size_bytes,
        object_key=object_key,
        file_type=file_type,
        storage_provider=storage_provider,
        file_object_id=file_object_id,
    )
    session.add(fo)
    return fo


def save_file_object(session: Session, file_object: FileObject) -> None:
    session.add(file_object)


def create_kb_file(
    session: Session,
    *,
    kb_id: str,
    file_object_id: str,
    original_filename: str,
    uploaded_by: str,
    status: str = "active",
) -> KbFile:
    kb_file = KbFile(
        kb_id=kb_id,
        file_object_id=file_object_id,
        original_filename=original_filename,
        uploaded_by=uploaded_by,
        status=status,
    )
    session.add(kb_file)
    return kb_file


def create_document(
    session: Session,
    *,
    kb_id: str,
    kb_file_id: str,
    title: str,
    status: str = "draft",
    version: int = 1,
    folder_id: str | None = None,
    folder_path: str | None = None,
) -> Document:
    document = Document(
        kb_id=kb_id,
        kb_file_id=kb_file_id,
        title=title,
        status=status,
        version=version,
        folder_id=folder_id,
        folder_path=folder_path,
    )
    session.add(document)
    return document


def save_kb_file(session: Session, kb_file: KbFile) -> None:
    session.add(kb_file)


def save_document(session: Session, document: Document) -> None:
    session.add(document)


def list_documents_with_folder(session: Session, kb_id: str) -> list[Document]:
    return list(
        session.exec(
            select(Document).where(Document.kb_id == kb_id, Document.folder_id.is_not(None))
        ).all()
    )


def set_document_thumbnail_key(session: Session, document: Document, thumbnail_key: str) -> None:
    document.thumbnail_key = thumbnail_key
    document.updated_at = utc_now()
    session.add(document)


def list_documents(
    session: Session,
    kb_id: str,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
    folder_path_filter: str | None = None,
    folder_id_filter: str | None = None,
) -> tuple[list[Document], int]:
    base = select(Document).where(Document.kb_id == kb_id)
    if status_filter:
        base = base.where(Document.status == status_filter)
    if folder_id_filter is not None:
        base = base.where(Document.folder_id == folder_id_filter)
    elif folder_path_filter is not None:
        base = base.where(Document.folder_path == folder_path_filter)
    total = session.exec(
        select(func.count()).select_from(base.subquery())
    ).one()
    items = session.exec(
        base.order_by(Document.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
    ).all()
    return list(items), int(total)


def find_document(
    session: Session,
    kb_id: str,
    folder_path: str | None,
    doc_title: str,
    *,
    folder_id: str | None = None,
) -> Document | None:
    if folder_id is not None:
        return session.exec(
            select(Document).where(
                Document.kb_id == kb_id,
                Document.folder_id == folder_id,
                Document.title == doc_title,
            )
        ).first()
    return session.exec(
        select(Document).where(
            Document.kb_id == kb_id,
            Document.folder_path == folder_path,
            Document.title == doc_title,
        )
    ).first()


def get_file_object_by_sha256(session: Session, sha256: str) -> FileObject | None:
    return session.exec(select(FileObject).where(FileObject.sha256 == sha256)).first()


def unlink_file_object_if_unused(session: Session, file_object_id: str) -> str | None:
    """若无 KbFile 引用则删除 FileObject，返回待删的磁盘路径（事务提交后删文件）"""
    if session.exec(select(KbFile).where(KbFile.file_object_id == file_object_id)).first():
        return None
    fo = session.get(FileObject, file_object_id)
    if not fo:
        return None
    path = fo.object_key
    session.delete(fo)
    return path


def delete_document_cascade(session: Session, document_id: str) -> tuple[str | None, str | None]:
    """
    级联删除文档及其关联数据（jobs/chunks/kb_file/file_object）

    Returns:
        (pdf_object_key, thumbnail_key) 待删除的对象 key（如有），需在 commit 后手动清理
    """
    doc = session.get(Document, document_id)
    if not doc:
        return None, None

    kb_file_id = doc.kb_file_id
    object_key_to_remove: str | None = None
    thumbnail_key_to_remove: str | None = (doc.thumbnail_key or "").strip() or None

    for chunk in session.exec(select(Chunk).where(Chunk.document_id == document_id)).all():
        session.delete(chunk)

    session.delete(doc)

    if kb_file_id:
        kb_file = session.get(KbFile, kb_file_id)
        if kb_file:
            file_object_id = kb_file.file_object_id
            session.delete(kb_file)

            if file_object_id:
                still_ref = (
                    session.exec(
                        select(KbFile).where(
                            KbFile.file_object_id == file_object_id,
                            KbFile.id != kb_file_id,
                        )
                    )
                    .first()
                )
                if not still_ref:
                    file_obj = session.get(FileObject, file_object_id)
                    if file_obj:
                        object_key_to_remove = file_obj.object_key
                        session.delete(file_obj)

    return object_key_to_remove, thumbnail_key_to_remove


def delete_chunks_by_document_id(session: Session, document_id: str) -> None:
    for chunk in session.exec(select(Chunk).where(Chunk.document_id == document_id)).all():
        session.delete(chunk)


def delete_chunks_for_document_ids(session: Session, document_ids: list[str]) -> None:
    if not document_ids:
        return
    for chunk in session.exec(select(Chunk).where(Chunk.document_id.in_(document_ids))).all():
        session.delete(chunk)

def has_any_document(session: Session, kb_id: str) -> bool:
    return (
        session.exec(
            select(func.count()).select_from(
                select(Document.id).where(Document.kb_id == kb_id).subquery()
            )
        ).one()
    ) > 0


def set_document_status(session: Session, document_id: str, status: str) -> None:
    doc = session.get(Document, document_id)
    if doc:
        doc.status = status
        session.add(doc)


def fail_documents_in_indexing(session: Session, kb_id: str) -> None:
    for doc in session.exec(
        select(Document).where(Document.kb_id == kb_id, Document.status == "indexing")
    ).all():
        doc.status = "failed"
        session.add(doc)


def resolve_document_file(session: Session, document_id: str) -> tuple[str, str]:
    """返回 (object_key, original_filename)。"""
    document = session.get(Document, document_id)
    if not document or not document.kb_file_id:
        raise RuntimeError(f"document or kb_file missing: {document_id}")
    kb_file = session.get(KbFile, document.kb_file_id)
    if not kb_file:
        raise RuntimeError(f"kb_file missing: {document_id}")
    file_object = session.get(FileObject, kb_file.file_object_id)
    if not file_object or not file_object.object_key:
        raise RuntimeError(f"file object missing: {document_id}")
    return file_object.object_key, kb_file.original_filename or "unknown"


def has_any_chunk(session: Session, kb_id: str) -> bool:
    """
    判断知识库是否存在可检索内容（至少 1 个 chunk）。

    用于区分：
    - 有文档但解析不到文本（chunks=0）
    - 真正空知识库（documents=0）
    """
    return (
        session.exec(
            select(func.count())
            .select_from(Chunk)
            .join(Document, Document.id == Chunk.document_id)
            .where(Document.kb_id == kb_id)
        ).one()
    ) > 0