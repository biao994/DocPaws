"""
数据库引擎与 Session 管理

提供 engine 单例、get_session 依赖注入、create_tables 等基础能力。
支持 SQLite（默认）与 PostgreSQL（DATABASE_URL）。
"""
import os
from contextlib import contextmanager
from typing import Iterator

from sqlmodel import SQLModel, Session, create_engine

from docpaws.settings import settings


def get_engine():
    """创建数据库引擎（单例）"""
    url = settings.database_url
    kwargs: dict = {}
    if settings.is_sqlite:
        db_path = url.removeprefix("sqlite:///")
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "5"))
        kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    return create_engine(url, **kwargs)


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
