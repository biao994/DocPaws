"""
API 依赖注入：db session、request_id 等
"""
from sqlmodel import Session

from docpaws.infra.db.session import get_session as _get_session
from docpaws.api.response import ErrorCode
from fastapi import Request, Depends

from docpaws.domain.models.user import User
from docpaws.errors import AppError


async def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


DependsSession = Depends(_get_session)
"""FastAPI 依赖注入的数据库 session 快捷引用"""


def get_current_user(
    request: Request,
    session: Session = DependsSession,
) -> User:
    """从 Cookie Session 读取 user_id，校验后返回 User。未登录返回 401。"""
    uid = request.session.get("user_id")
    if not uid:
        raise AppError(
            error_code=ErrorCode.UNAUTHORIZED,
            message="未登录",
            status_code=401,
        )
    user = session.get(User, uid)
    if not user:
        request.session.clear()
        raise AppError(
            error_code=ErrorCode.UNAUTHORIZED,
            message="登录已失效，请重新登录",
            status_code=401,
        )
    return user


def get_document_service(session: Session = DependsSession):
    from docpaws.usecases.document_service import DocumentService

    return DocumentService(session)


def get_conversation_service(session: Session = DependsSession):
    from docpaws.usecases.conversation_service import ConversationService

    return ConversationService(session)


def get_chat_service(session: Session = DependsSession):
    from docpaws.usecases.chat_service import ChatService
    from docpaws.infra.cache.redis_client import get_cache_redis

    return ChatService(session, cache_redis=get_cache_redis())


def get_kb_service(session: Session = DependsSession):
    from docpaws.usecases.kb_service import KbService

    return KbService(session)


def get_index_service(session: Session = DependsSession):
    from docpaws.usecases.index_service import IndexService

    return IndexService(session)


def get_feedback_service(session: Session = DependsSession):
    from docpaws.usecases.feedback_service import FeedbackService

    return FeedbackService(session)


def get_auth_service(session: Session = DependsSession):
    from docpaws.usecases.auth_service import AuthService

    return AuthService(session)


def get_folder_service(session: Session = DependsSession):
    from docpaws.usecases.folder_service import FolderService

    return FolderService(session)
