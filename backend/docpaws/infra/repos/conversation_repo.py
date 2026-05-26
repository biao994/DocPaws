"""
会话 Repo（infra 实现）
"""

from sqlalchemy import func, or_
from sqlmodel import Session, select

from docpaws.domain.models.chat import Conversation, Message


def _apply_scope_filter(stmt, *, scope_type: str, scope_id: str | None):
    stmt = stmt.where(Conversation.scope_type == scope_type)
    if scope_type == "kb":
        return stmt.where(or_(Conversation.scope_id.is_(None), Conversation.scope_id == ""))
    if scope_id:
        return stmt.where(Conversation.scope_id == scope_id)
    return stmt.where(Conversation.scope_id.is_(None))


def get_conversation_by_id(session: Session, conversation_id: str) -> Conversation | None:
    return session.get(Conversation, conversation_id)


def create_conversation(
    session: Session,
    kb_id: str,
    user_id: str,
    title_hint: str = "新对话",
    *,
    scope_type: str = "kb",
    scope_id: str | None = None,
) -> Conversation:
    c = Conversation(
        kb_id=kb_id,
        user_id=user_id,
        title=title_hint[:30] or "新对话",
        scope_type=scope_type,
        scope_id=scope_id,
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def list_conversations(
    session: Session,
    kb_id: str,
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    *,
    scope_type: str | None = None,
    scope_id: str | None = None,
) -> tuple[list[Conversation], int]:
    base = select(Conversation).where(
        Conversation.kb_id == kb_id,
        Conversation.user_id == user_id,
    )
    if scope_type:
        base = _apply_scope_filter(base, scope_type=scope_type, scope_id=scope_id)
    total = session.exec(select(func.count()).select_from(base.subquery())).one()
    stmt = (
        base.order_by(Conversation.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = session.exec(stmt).all()
    return list(items), int(total)


def list_all_conversations(
    session: Session,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Conversation], int]:
    count_stmt = select(Conversation)
    total = len(session.exec(count_stmt).all())
    stmt = (
        select(Conversation)
        .order_by(Conversation.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = session.exec(stmt).all()
    return list(items), total


def list_all_conversations_for_user(
    session: Session,
    user_id: str,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Conversation], int]:
    count_stmt = select(Conversation).where(Conversation.user_id == user_id)
    total = len(session.exec(count_stmt).all())
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = session.exec(stmt).all()
    return list(items), total


def get_messages_for_conversation(session: Session, conversation_id: str) -> list[Message]:
    return list(
        session.exec(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        ).all()
    )


def get_recent_history_text(session: Session, conversation_id: str, limit: int = 10) -> str:
    if not conversation_id:
        return ""

    messages = (
        session.exec(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(limit)
        )
        .all()
    )
    if not messages:
        return ""

    messages.reverse()
    history_lines: list[str] = []
    for msg in messages:
        role_label = "用户" if msg.role == "user" else "助手"
        history_lines.append(f"{role_label}: {msg.content}")
    return "\n".join(history_lines)


def delete_conversation_cascade(session: Session, conversation_id: str) -> bool:
    c = session.get(Conversation, conversation_id)
    if not c:
        return False
    for msg in session.exec(select(Message).where(Message.conversation_id == conversation_id)).all():
        session.delete(msg)
    session.delete(c)
    return True

