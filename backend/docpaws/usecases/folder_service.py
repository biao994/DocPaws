"""
文件夹业务：创建 / 列表 / 重命名 / 删除
"""
from __future__ import annotations

from sqlmodel import Session

from docpaws.api.response import ErrorCode
from docpaws.domain.datetime_utils import utc_now
from docpaws.errors import AppError
from docpaws.domain.models.document import Document
from docpaws.infra.repos.folder_repo import (
    count_child_folders,
    count_documents_in_folder,
    create_folder,
    delete_folder_row,
    find_folder_by_parent_name,
    folder_materialized_path,
    get_folder_by_id,
    get_or_create_folder_by_path,
    list_child_folders,
    list_folders_by_kb,
    update_folder_name,
)
from docpaws.infra.repos.kb_repo import get_kb_by_id
from docpaws.usecases.document_service import normalize_folder_path


def _folder_to_dict(session: Session, folder) -> dict:
    path = folder_materialized_path(session, folder.id)
    return {
        "id": folder.id,
        "kb_id": folder.kb_id,
        "parent_id": folder.parent_id,
        "name": folder.name,
        "path": path or None,
        "created_at": folder.created_at,
        "updated_at": folder.updated_at,
    }


def resolve_folder_for_document(
    session: Session,
    kb_id: str,
    *,
    folder_id: str | None = None,
    folder_path: str | None = None,
) -> tuple[str | None, str | None]:
    """
    返回 (folder_id, folder_path 物化路径)。
    folder_id 优先；仅 folder_path 时自动建树。
    """
    if folder_id:
        folder = get_folder_by_id(session, folder_id)
        if not folder or folder.kb_id != kb_id:
            raise AppError(error_code=ErrorCode.FOLDER_NOT_FOUND, message="文件夹不存在", status_code=404)
        path = folder_materialized_path(session, folder.id) or None
        return folder.id, path
    fp = normalize_folder_path(folder_path)
    if not fp:
        return None, None
    fid = get_or_create_folder_by_path(session, kb_id, fp)
    return fid, fp


def refresh_kb_document_folder_paths(session: Session, kb_id: str) -> None:
    """按 folder_id 重算该 KB 下所有文档的 folder_path 缓存"""
    from sqlmodel import select

    docs = list(
        session.exec(
            select(Document).where(Document.kb_id == kb_id, Document.folder_id.is_not(None))
        ).all()
    )
    for doc in docs:
        if not doc.folder_id:
            continue
        doc.folder_path = folder_materialized_path(session, doc.folder_id) or None
        doc.updated_at = utc_now()
        session.add(doc)


class FolderService:
    def __init__(self, session: Session):
        self.session = session

    def list_folders(self, *, kb_id: str, parent_id: str | None = None) -> list[dict]:
        if not get_kb_by_id(self.session, kb_id):
            raise AppError(error_code=ErrorCode.KB_NOT_FOUND, message="知识库不存在", status_code=404)
        if parent_id is not None:
            parent = get_folder_by_id(self.session, parent_id)
            if not parent or parent.kb_id != kb_id:
                raise AppError(error_code=ErrorCode.FOLDER_NOT_FOUND, message="父文件夹不存在", status_code=404)
            items = list_child_folders(self.session, kb_id, parent_id)
        else:
            items = list_folders_by_kb(self.session, kb_id)
        return [_folder_to_dict(self.session, f) for f in items]

    def create_folder(
        self,
        *,
        kb_id: str,
        name: str,
        parent_id: str | None = None,
    ) -> dict:
        if not get_kb_by_id(self.session, kb_id):
            raise AppError(error_code=ErrorCode.KB_NOT_FOUND, message="知识库不存在", status_code=404)
        clean = (name or "").strip()
        if not clean:
            raise AppError(error_code=ErrorCode.VALIDATION_ERROR, message="文件夹名称不能为空", status_code=400)
        if "/" in clean or "\\" in clean:
            raise AppError(error_code=ErrorCode.VALIDATION_ERROR, message='文件夹名称不能包含 "/"', status_code=400)
        if parent_id:
            parent = get_folder_by_id(self.session, parent_id)
            if not parent or parent.kb_id != kb_id:
                raise AppError(error_code=ErrorCode.FOLDER_NOT_FOUND, message="父文件夹不存在", status_code=404)
        if find_folder_by_parent_name(self.session, kb_id, parent_id, clean):
            raise AppError(error_code=ErrorCode.NAME_CONFLICT, message="同级已存在同名文件夹", status_code=409)
        folder = create_folder(self.session, kb_id=kb_id, name=clean, parent_id=parent_id)
        self.session.commit()
        self.session.refresh(folder)
        return _folder_to_dict(self.session, folder)

    def rename_folder(self, *, folder_id: str, name: str) -> dict:
        folder = get_folder_by_id(self.session, folder_id)
        if not folder:
            raise AppError(error_code=ErrorCode.FOLDER_NOT_FOUND, message="文件夹不存在", status_code=404)
        clean = (name or "").strip()
        if not clean:
            raise AppError(error_code=ErrorCode.VALIDATION_ERROR, message="文件夹名称不能为空", status_code=400)
        if "/" in clean or "\\" in clean:
            raise AppError(error_code=ErrorCode.VALIDATION_ERROR, message='文件夹名称不能包含 "/"', status_code=400)
        if clean == folder.name:
            return _folder_to_dict(self.session, folder)
        conflict = find_folder_by_parent_name(self.session, folder.kb_id, folder.parent_id, clean)
        if conflict and conflict.id != folder.id:
            raise AppError(error_code=ErrorCode.NAME_CONFLICT, message="同级已存在同名文件夹", status_code=409)
        update_folder_name(self.session, folder, clean)
        refresh_kb_document_folder_paths(self.session, folder.kb_id)
        self.session.commit()
        self.session.refresh(folder)
        return _folder_to_dict(self.session, folder)

    def delete_folder(self, *, folder_id: str) -> dict:
        folder = get_folder_by_id(self.session, folder_id)
        if not folder:
            raise AppError(error_code=ErrorCode.FOLDER_NOT_FOUND, message="文件夹不存在", status_code=404)
        if count_documents_in_folder(self.session, folder_id) > 0:
            raise AppError(error_code=ErrorCode.FOLDER_NOT_EMPTY, message="文件夹非空，无法删除", status_code=409)
        if count_child_folders(self.session, folder_id) > 0:
            raise AppError(error_code=ErrorCode.FOLDER_NOT_EMPTY, message="存在子文件夹，无法删除", status_code=409)
        delete_folder_row(self.session, folder)
        self.session.commit()
        return {"status": "deleted", "folder_id": folder_id}
