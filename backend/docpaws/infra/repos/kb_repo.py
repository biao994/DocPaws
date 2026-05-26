"""
知识库 Repo（infra 实现）
"""

from sqlmodel import Session, select

from docpaws.domain.models.kb import KnowledgeBase


def get_kb_by_id(session: Session, kb_id: str) -> KnowledgeBase | None:
    return session.get(KnowledgeBase, kb_id)


def list_kbs(
    session: Session,
    owner_user_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[KnowledgeBase], int]:
    stmt = select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc())
    if owner_user_id:
        stmt = stmt.where(KnowledgeBase.owner_user_id == owner_user_id)
    count_stmt = select(KnowledgeBase)
    if owner_user_id:
        count_stmt = count_stmt.where(KnowledgeBase.owner_user_id == owner_user_id)
    total = len(session.exec(count_stmt).all())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    items = session.exec(stmt).all()
    return list(items), total


def delete_kb(session: Session, kb_id: str) -> bool:
    kb = session.get(KnowledgeBase, kb_id)
    if not kb:
        return False
    session.delete(kb)
    return True


def update_kb(
    session: Session,
    kb_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
) -> KnowledgeBase | None:
    kb = session.get(KnowledgeBase, kb_id)
    if not kb:
        return None
    if name is not None:
        kb.name = name
    if description is not None:
        kb.description = description
    session.add(kb)
    return kb

