"""
知识库业务编排
"""
from sqlmodel import Session

from docpaws.domain.models.kb import KnowledgeBase
from docpaws.api.schemas.kb import KbData, KbListData


def _create_kb_impl(
    session: Session,
    *,
    name: str,
    description: str | None = None,
    owner_user_id: str,
) -> dict:
    kb = KnowledgeBase(
        name=name,
        description=description,
        owner_user_id=owner_user_id,
    )
    session.add(kb)
    session.commit()
    session.refresh(kb)
    return _to_data(kb)


def _get_kb_by_id_impl(session: Session, kb_id: str) -> dict | None:
    from docpaws.infra.repos.kb_repo import get_kb_by_id as _get
    kb = _get(session, kb_id)
    return _to_data(kb) if kb else None


def _list_kbs_impl(
    session: Session,
    owner_user_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    from docpaws.infra.repos.kb_repo import list_kbs as _list
    items, total = _list(session, owner_user_id, page, page_size)
    return KbListData(
        items=[KbData(**_to_data(kb)) for kb in items],
        page=page,
        page_size=page_size,
        total=total,
    ).model_dump()


def _remove_kb_impl(session: Session, kb_id: str) -> bool:
    from docpaws.infra.repos.kb_repo import delete_kb as _delete
    ok = _delete(session, kb_id)
    if ok:
        session.commit()
    return ok


def _update_kb_impl(
    session: Session,
    kb_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
) -> dict | None:
    from docpaws.infra.repos.kb_repo import update_kb as _update
    kb = _update(session, kb_id, name=name, description=description)
    if not kb:
        return None
    session.commit()
    session.refresh(kb)
    return _to_data(kb)


def _to_data(kb: KnowledgeBase) -> dict:
    return KbData(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        owner_user_id=kb.owner_user_id,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    ).model_dump()


class KbService:
    def __init__(self, session: Session):
        self.session = session

    def create_kb(
        self,
        *,
        name: str,
        description: str | None = None,
        owner_user_id: str,
    ) -> dict:
        return _create_kb_impl(
            self.session,
            name=name,
            description=description,
            owner_user_id=owner_user_id,
        )

    def get_kb_by_id(self, *, kb_id: str) -> dict | None:
        return _get_kb_by_id_impl(self.session, kb_id)

    def list_kbs(
        self,
        *,
        owner_user_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        return _list_kbs_impl(self.session, owner_user_id, page, page_size)

    def remove_kb(self, *, kb_id: str) -> bool:
        return _remove_kb_impl(self.session, kb_id)

    def update_kb(
        self,
        *,
        kb_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> dict | None:
        return _update_kb_impl(self.session, kb_id, name=name, description=description)
