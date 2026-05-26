from __future__ import annotations

import importlib
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session


# 确保 pytest 从 backend/ 根目录能 import docpaws（在收集阶段就生效）
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """
    为每个测试用例提供隔离的 FastAPI client：
    - 独立 sqlite 数据库文件（放在 tmp_path）
    - 独立 data/uploads/index 目录（放在 tmp_path）

    这样跑测试不会污染真实开发数据与本机目录。
    """
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

    # 关键：engine 在模块 import 时初始化，需要 reload 才能使用新的 DB_PATH/目录
    import docpaws.infra.db.session as db_session
    importlib.reload(db_session)

    import docpaws.app as docpaws_app
    importlib.reload(docpaws_app)

    app = docpaws_app.create_app()
    # 用上下文管理器触发 startup/shutdown（否则 on_event 启动事件不会执行，DB 表也不会创建）
    with TestClient(app) as c:
        yield c


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
def db_session(client) -> Session:
    """
    直接访问当前测试 app 使用的 DB session（用于断言级联删除/产物写入等）。
    必须通过 client fixture 先于本 fixture 运行，以确保 settings/engine 已按 tmp_path reload。
    """
    from docpaws.infra.db.session import engine

    with Session(engine) as s:
        yield s

