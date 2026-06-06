from __future__ import annotations

import importlib
import os
import sys
import uuid
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

# 确保 pytest 从 backend/ 根目录能 import docpaws（在收集阶段就生效）
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

DEFAULT_PG_TEST_URL = (
    "postgresql+psycopg://docpaws:docpaws@127.0.0.1:5432/docpaws_test"
)


def _build_test_client(tmp_path: Path, database_url: str) -> Iterator[TestClient]:
    from docpaws.settings import settings

    data_dir = tmp_path / "data"
    uploads_dir = data_dir / "uploads"
    index_dir = tmp_path / "indexes"

    data_dir.mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    index_dir.mkdir(parents=True, exist_ok=True)

    settings.DATA_DIR = str(data_dir)
    settings.DB_PATH = str(data_dir / "test_docpaws.db")
    settings.UPLOAD_DIR = str(uploads_dir)
    settings.INDEX_DIR = str(index_dir)
    settings.SECRET_KEY = "pytest-secret-key-at-least-32-characters-long"
    settings._database_url = database_url

    import docpaws.infra.db.session as db_session

    importlib.reload(db_session)

    import docpaws.app as docpaws_app

    importlib.reload(docpaws_app)

    app = docpaws_app.create_app()
    with TestClient(app) as c:
        yield c


def _pg_reachable(url: str) -> bool:
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


@pytest.fixture()
def client(tmp_path: Path) -> Iterator[TestClient]:
    """
    为每个测试用例提供隔离的 FastAPI client：
    - 独立 sqlite 数据库文件（放在 tmp_path）
    - 独立 data/uploads/index 目录（放在 tmp_path）

    这样跑测试不会污染真实开发数据与本机目录。
    """
    db_path = tmp_path / "data" / "test_docpaws.db"
    yield from _build_test_client(tmp_path, f"sqlite:///{db_path}")


@pytest.fixture()
def pg_client(tmp_path: Path) -> Iterator[TestClient]:
    """PostgreSQL 集成测试 client（需 docker postgres + RUN_PG_INTEGRATION=1）。"""
    if os.getenv("RUN_PG_INTEGRATION") != "1":
        pytest.skip("PG integration test; set RUN_PG_INTEGRATION=1")

    url = os.getenv("PG_TEST_DATABASE_URL", DEFAULT_PG_TEST_URL).strip()
    if not _pg_reachable(url):
        pytest.skip(
            f"PostgreSQL not reachable at {url}; run `docker compose up -d postgres`"
        )
    yield from _build_test_client(tmp_path, url)


@pytest.fixture()
def auth_client(client):
    """已注册并已登录会话的客户端（Cookie Session）。"""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"t_{uuid.uuid4().hex[:12]}@example.com",
            "username": f"u{uuid.uuid4().hex[:8]}",
            "password": "testpass1234",
        },
    )
    assert reg.status_code == 200, reg.text
    return client


@pytest.fixture()
def pg_auth_client(pg_client):
    """PG 集成测试：已登录 client。"""
    reg = pg_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"pg_{uuid.uuid4().hex[:12]}@example.com",
            "username": f"pg{uuid.uuid4().hex[:8]}",
            "password": "testpass1234",
        },
    )
    assert reg.status_code == 200, reg.text
    return pg_client


@pytest.fixture()
def db_session(client) -> Session:
    """
    直接访问当前测试 app 使用的 DB session（用于断言级联删除/产物写入等）。
    必须通过 client fixture 先于本 fixture 运行，以确保 settings/engine 已按 tmp_path reload。
    """
    from docpaws.infra.db.session import engine

    with Session(engine) as s:
        yield s


@pytest.fixture()
def pg_db_session(pg_client) -> Session:
    from docpaws.infra.db.session import engine

    with Session(engine) as s:
        yield s
