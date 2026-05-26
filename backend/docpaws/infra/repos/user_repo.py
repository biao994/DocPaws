"""
用户 Repo：User 表的查询与持久化
"""
from sqlmodel import Session, select

from docpaws.domain.models.user import User


def normalize_email(email: str) -> str:
    return str(email).strip().lower()


def normalize_username(username: str) -> str:
    return str(username).strip()


def get_user_by_email(session: Session, email: str) -> User | None:
    e = normalize_email(email)
    return session.exec(select(User).where(User.email == e)).first()


def get_user_by_username(session: Session, username: str) -> User | None:
    u = normalize_username(username)
    return session.exec(select(User).where(User.username == u)).first()


def create_user(
    session: Session,
    *,
    email: str,
    username: str,
    password_hash: str,
) -> User:
    user = User(
        email=normalize_email(email),
        username=normalize_username(username),
        password_hash=password_hash,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
