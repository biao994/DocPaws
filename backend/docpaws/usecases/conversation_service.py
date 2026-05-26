"""
会话相关业务编排
"""

from sqlmodel import Session

from docpaws.errors import AppError
from docpaws.api.response import ErrorCode, get_status_code
from docpaws.api.authz import require_kb_owned


def _assert_conversation_user(conv, user_id: str) -> None:
    """无会话 404；有会话但非本人 403"""
    if not conv:
        raise AppError(
            error_code=ErrorCode.CONVERSATION_NOT_FOUND,
            message="会话不存在",
            status_code=get_status_code(ErrorCode.CONVERSATION_NOT_FOUND),
        )
    if conv.user_id != user_id:
        raise AppError(
            error_code=ErrorCode.FORBIDDEN,
            message="无权访问该会话",
            status_code=get_status_code(ErrorCode.FORBIDDEN),
        )


def _delete_conversation_impl(session: Session, conversation_id: str) -> bool:
    from docpaws.infra.repos.conversation_repo import delete_conversation_cascade

    ok = delete_conversation_cascade(session, conversation_id)
    if not ok:
        return False
    session.commit()
    return True


def _to_conversation_data(c) -> dict:
    from docpaws.api.schemas.conversations import ConversationData

    return ConversationData(
        id=c.id,
        kb_id=c.kb_id,
        title=c.title,
        scope_type=getattr(c, "scope_type", None) or "kb",
        scope_id=getattr(c, "scope_id", None),
        created_at=c.created_at,
        updated_at=c.updated_at,
    ).model_dump()


def _to_message_data(session: Session, m) -> dict:
    from docpaws.api.schemas.conversations import CitationData, MessageData
    from docpaws.domain.models.index import Answer
    from docpaws.usecases.chat_service import hydrate_citations_from_stored

    citations: list = []
    if m.answer_id:
        answer = session.get(Answer, m.answer_id)
        if answer:
            citations = hydrate_citations_from_stored(session, answer.citations)

    return MessageData(
        id=m.id,
        role=m.role,
        content=m.content,
        answer_id=m.answer_id,
        created_at=m.created_at,
        citations=[CitationData(**c) for c in citations],
    ).model_dump()


def _to_conversation_data_with_messages(session: Session, c, messages) -> dict:
    from docpaws.api.schemas.conversations import ConversationData

    return ConversationData(
        id=c.id,
        kb_id=c.kb_id,
        title=c.title,
        scope_type=getattr(c, "scope_type", None) or "kb",
        scope_id=getattr(c, "scope_id", None),
        created_at=c.created_at,
        updated_at=c.updated_at,
        messages=[_to_message_data(session, m) for m in messages],
    ).model_dump()


class ConversationService:
    def __init__(self, session: Session):
        self.session = session

    def list_conversations(
        self,
        *,
        kb_id: str,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        scope_type: str | None = None,
        scope_id: str | None = None,
    ) -> tuple[list[dict], int]:
        from docpaws.infra.repos.conversation_repo import list_conversations

        require_kb_owned(self.session, kb_id, user_id)

        items, total = list_conversations(
            self.session,
            kb_id,
            user_id,
            page,
            page_size,
            scope_type=scope_type,
            scope_id=scope_id,
        )
        return ([_to_conversation_data(c) for c in items], total)

    def get_conversation(self, *, conversation_id: str, user_id: str) -> dict:
        from docpaws.infra.repos.conversation_repo import get_conversation_by_id, get_messages_for_conversation

        conv = get_conversation_by_id(self.session, conversation_id)
        _assert_conversation_user(conv, user_id)

        messages = get_messages_for_conversation(self.session, conversation_id)
        return _to_conversation_data_with_messages(self.session, conv, messages)

    def list_all_conversations(
        self, *, user_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict], int]:
        from docpaws.infra.repos.conversation_repo import list_all_conversations_for_user

        items, total = list_all_conversations_for_user(self.session, user_id, page, page_size)
        return ([_to_conversation_data(c) for c in items], total)

    def delete_conversation(self, *, conversation_id: str, user_id: str) -> bool:
        from docpaws.infra.repos.conversation_repo import get_conversation_by_id

        conv = get_conversation_by_id(self.session, conversation_id)
        _assert_conversation_user(conv, user_id)

        ok = _delete_conversation_impl(self.session, conversation_id)
        if not ok:
            raise AppError(
                error_code=ErrorCode.CONVERSATION_NOT_FOUND,
                message="会话不存在",
                status_code=get_status_code(ErrorCode.CONVERSATION_NOT_FOUND),
            )
        return True

