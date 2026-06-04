"""
文件夹 Repo
"""
from __future__ import annotations

from sqlmodel import Session, select

from docpaws.domain.datetime_utils import utc_now
from docpaws.domain.models.document import Document
from docpaws.domain.models.folder import KbFolder


def get_folder_by_id(session: Session, folder_id: str) -> KbFolder | None:
    return session.get(KbFolder, folder_id)


def list_folders_by_kb(session: Session, kb_id: str) -> list[KbFolder]:
    return list(
        session.exec(
            select(KbFolder).where(KbFolder.kb_id == kb_id).order_by(KbFolder.created_at.asc())
        ).all()
    )


def find_folder_by_parent_name(
    session: Session,
    kb_id: str,
    parent_id: str | None,
    name: str,
) -> KbFolder | None:
    stmt = select(KbFolder).where(KbFolder.kb_id == kb_id, KbFolder.name == name)
    if parent_id is None:
        stmt = stmt.where(KbFolder.parent_id.is_(None))
    else:
        stmt = stmt.where(KbFolder.parent_id == parent_id)
    return session.exec(stmt).first()


def create_folder(
    session: Session,
    *,
    kb_id: str,
    name: str,
    parent_id: str | None = None,
) -> KbFolder:
    folder = KbFolder(kb_id=kb_id, name=name.strip(), parent_id=parent_id)
    session.add(folder)
    session.flush()
    return folder


def folder_materialized_path(session: Session, folder_id: str) -> str:
    """从 folder_id 向上拼接完整路径，如 `资料/2023`"""
    parts: list[str] = []
    current_id: str | None = folder_id
    seen: set[str] = set()
    while current_id:
        if current_id in seen:
            break
        seen.add(current_id)
        folder = session.get(KbFolder, current_id)
        if not folder:
            break
        parts.append(folder.name)
        current_id = folder.parent_id
    parts.reverse()
    return "/".join(parts)


def list_child_folders(session: Session, kb_id: str, parent_id: str | None) -> list[KbFolder]:
    stmt = select(KbFolder).where(KbFolder.kb_id == kb_id)
    if parent_id is None:
        stmt = stmt.where(KbFolder.parent_id.is_(None))
    else:
        stmt = stmt.where(KbFolder.parent_id == parent_id)
    return list(session.exec(stmt.order_by(KbFolder.name.asc())).all())


def count_documents_in_folder(session: Session, folder_id: str) -> int:
    from sqlalchemy import func

    return int(
        session.exec(
            select(func.count()).select_from(Document).where(Document.folder_id == folder_id)
        ).one()
    )


def count_child_folders(session: Session, parent_id: str) -> int:
    from sqlalchemy import func

    return int(
        session.exec(
            select(func.count()).select_from(KbFolder).where(KbFolder.parent_id == parent_id)
        ).one()
    )


def get_or_create_folder_by_path(session: Session, kb_id: str, folder_path: str | None) -> str | None:
    """
    按 `a/b/c` 路径逐级 get_or_create，返回叶子 folder_id；空路径返回 None。
    """
    if not folder_path:
        return None
    parts = [p for p in folder_path.split("/") if p]
    if not parts:
        return None
    parent_id: str | None = None
    leaf_id: str | None = None
    for part in parts:
        existing = find_folder_by_parent_name(session, kb_id, parent_id, part)
        if existing:
            leaf_id = existing.id
            parent_id = existing.id
        else:
            created = create_folder(session, kb_id=kb_id, name=part, parent_id=parent_id)
            leaf_id = created.id
            parent_id = created.id
    return leaf_id


def list_documents_by_folder_id(session: Session, folder_id: str) -> list[Document]:
    return list(session.exec(select(Document).where(Document.folder_id == folder_id)).all())


def collect_folder_ids_with_descendants(
    session: Session, kb_id: str, root_folder_id: str
) -> list[str]:
    """返回 root 及其所有子文件夹 id（含多级嵌套）。"""
    folders = list_folders_by_kb(session, kb_id)
    children_by_parent: dict[str | None, list[str]] = {}
    folder_kb: dict[str, str] = {}
    for f in folders:
        folder_kb[f.id] = f.kb_id
        children_by_parent.setdefault(f.parent_id, []).append(f.id)

    if root_folder_id not in folder_kb or folder_kb[root_folder_id] != kb_id:
        return []

    ordered: list[str] = []
    seen: set[str] = set()
    stack = [root_folder_id]
    while stack:
        fid = stack.pop()
        if fid in seen:
            continue
        seen.add(fid)
        ordered.append(fid)
        for child_id in children_by_parent.get(fid, []):
            stack.append(child_id)
    return ordered


def list_documents_in_folder_tree(session: Session, kb_id: str, root_folder_id: str) -> list[Document]:
    """列出文件夹及其子文件夹下的全部文档。"""
    folder_ids = collect_folder_ids_with_descendants(session, kb_id, root_folder_id)
    if not folder_ids:
        return []
    return list(
        session.exec(
            select(Document).where(
                Document.kb_id == kb_id,
                Document.folder_id.in_(folder_ids),
            )
        ).all()
    )


def update_folder_name(session: Session, folder: KbFolder, new_name: str) -> None:
    folder.name = new_name.strip()
    folder.updated_at = utc_now()
    session.add(folder)


def delete_folder_row(session: Session, folder: KbFolder) -> None:
    session.delete(folder)
