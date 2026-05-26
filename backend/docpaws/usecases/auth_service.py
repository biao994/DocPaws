"""
注册 / 登录业务编排（不依赖 Request；Session Cookie 在路由层写入）
"""
from sqlmodel import Session

from docpaws.api.response import ErrorCode
from docpaws.domain.models.user import User
from docpaws.errors import AppError
from docpaws.infra.auth.password import hash_password, verify_password
from docpaws.infra.repos import user_repo


class AuthService:
    def __init__(self, session: Session):
        self._session = session

    def register(self, email: str, username: str, password: str) -> User:
        if user_repo.get_user_by_email(self._session, email):
            raise AppError(
                error_code=ErrorCode.EMAIL_ALREADY_REGISTERED,
                message="该邮箱已注册",
                status_code=409,
            )
        if user_repo.get_user_by_username(self._session, username):
            raise AppError(
                error_code=ErrorCode.NAME_CONFLICT,
                message="用户名已被占用",
                status_code=409,
            )
        return user_repo.create_user(
            self._session,
            email=email,
            username=username,
            password_hash=hash_password(password),
        )

    def login(self, email: str, password: str) -> User:
        user = user_repo.get_user_by_email(self._session, email)
        if not user or not verify_password(password, user.password_hash):
            raise AppError(
                error_code=ErrorCode.AUTH_INVALID_CREDENTIALS,
                message="邮箱或密码错误",
                status_code=401,
            )
        return user
