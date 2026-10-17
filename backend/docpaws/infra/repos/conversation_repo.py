"""
会话 Repo（infra 实现）
"""

from sqlalchemy import func, or_
from sqlmodel import Session, select

from docpaws.domain.models.chat import Conversation, Message
from docpaws.domain.models.index import Answer, RetrievalRun
from docpaws.domain.services.chat_history import format_history_for_prompt
from docpaws.settings import settings


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


def get_recent_history_text(
    session: Session,
    conversation_id: str,
    limit: int = 10,
    max_tokens: int | None = None,
    recent_keep: int | None = None,
    older_line_max: int | None = None,
) -> str:
    """拼最近若干条历史：近几轮原样，更早按 token 压缩，仍超预算再裁（max_tokens≤0 不裁）。"""
    if not conversation_id:
        return ""

    if max_tokens is None:
        max_tokens = settings.CHAT_HISTORY_MAX_TOKENS
    if recent_keep is None:
        recent_keep = settings.CHAT_HISTORY_RECENT_MESSAGES
    if older_line_max is None:
        older_line_max = settings.CHAT_HISTORY_OLDER_LINE_TOKENS

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

    return format_history_for_prompt(
        history_lines,
        max_tokens=max_tokens,
        recent_keep=recent_keep,
        older_line_max=older_line_max,
    )


def delete_conversation_cascade(session: Session, conversation_id: str) -> bool:
    c = session.get(Conversation, conversation_id)
    if not c:
        return False
    for msg in session.exec(select(Message).where(Message.conversation_id == conversation_id)).all():
        session.delete(msg)
    session.delete(c)
    return True


def get_answer_by_id(session: Session, answer_id: str) -> Answer | None:
    return session.get(Answer, answer_id)


def create_message(
    session: Session,
    *,
    conversation_id: str,
    role: str,
    content: str,
    answer_id: str | None = None,
    commit: bool = True,
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        answer_id=answer_id,
    )
    session.add(msg)
    if commit:
        session.commit()
        session.refresh(msg)
    else:
        session.flush()
    return msg


def create_answer(
    session: Session,
    *,
    conversation_id: str,
    question_message_id: str,
    answer_text: str,
    model_name: str,
    citations: list | None = None,
    version: int = 1,
    is_current: bool = True,
    commit: bool = True,
) -> Answer:
    answer = Answer(
        conversation_id=conversation_id,
        question_message_id=question_message_id,
        version=version,
        is_current=is_current,
        answer_text=answer_text,
        citations=citations if citations is not None else [],
        model_name=model_name,
    )
    session.add(answer)
    if commit:
        session.commit()
        session.refresh(answer)
    else:
        session.flush()
    return answer


def add_retrieval_run(
    session: Session,
    *,
    kb_id: str,
    conversation_id: str,
    question_message_id: str,
    query_text: str,
    top_k: int,
    hit_chunks,
) -> RetrievalRun:
    """仅 add，不 commit（与 Answer 同事务落库）。"""
    run = RetrievalRun(
        kb_id=kb_id,
        conversation_id=conversation_id,
        question_message_id=question_message_id,
        query_text=query_text,
        top_k=top_k,
        hit_chunks=hit_chunks,
    )
    session.add(run)
    return run


def persist_assistant_answer_and_message(
    session: Session,
    *,
    conversation_id: str,
    question_message_id: str,
    answer_text: str,
    model_name: str,
    citations: list | None = None,
    version: int = 1,
    is_current: bool = True,
) -> tuple[Answer, Message]:
    """Answer + 助手 Message 同事务落库（一次 commit）；挂着的 RetrievalRun 一并提交。"""
    answer = create_answer(
        session,
        conversation_id=conversation_id,
        question_message_id=question_message_id,
        answer_text=answer_text,
        model_name=model_name,
        citations=citations,
        version=version,
        is_current=is_current,
        commit=False,
    )
    assistant_msg = create_message(
        session,
        conversation_id=conversation_id,
        role="assistant",
        content=answer_text,
        answer_id=answer.id,
        commit=False,
    )
    session.commit()
    session.refresh(answer)
    session.refresh(assistant_msg)
    return answer, assistant_msg

