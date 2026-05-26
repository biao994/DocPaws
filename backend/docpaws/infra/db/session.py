"""
数据库引擎与 Session 管理

提供 engine 单例、get_session 依赖注入、create_tables 等基础能力。
"""
import os
from contextlib import contextmanager
from typing import Iterator

from sqlmodel import SQLModel, Session, create_engine

from docpaws.settings import settings


def _sqlite_url(db_path: str) -> str:
    return f"sqlite:///{db_path}"


def get_engine():
    """创建数据库引擎（单例）"""
    os.makedirs(os.path.dirname(settings.DB_PATH), exist_ok=True)
    return create_engine(
        _sqlite_url(settings.DB_PATH),
        connect_args={"check_same_thread": False},
    )


engine = get_engine()


def create_db_and_tables():
    # 确保所有 model 已注册到 metadata
    import docpaws.domain.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    from docpaws.infra.db.migrate import run_migrations

    run_migrations()


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def get_session() -> Iterator[Session]:
    """FastAPI Depends 用"""
    with Session(engine) as session:
        yield session
