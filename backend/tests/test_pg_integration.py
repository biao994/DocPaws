"""PostgreSQL 集成测试：验证生产库上的关键 API 链路。"""
from __future__ import annotations

import io

import pytest

pytestmark = pytest.mark.pg


def test_pg_healthz_reports_postgresql(pg_client):
    r = pg_client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert body.get("db") == "postgresql"


def test_pg_create_kb_then_list(pg_auth_client):
    r = pg_auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "pg-kb", "description": "pg integration"},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    r2 = pg_auth_client.get("/api/v1/knowledge-bases?page=1&page_size=20")
    assert r2.status_code == 200
    items = r2.json()["data"]["items"]
    assert any(x["id"] == kb_id for x in items)


def test_pg_upload_creates_index_job(pg_auth_client):
    r = pg_auth_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "pg-kb-upload", "description": ""},
    )
    assert r.status_code == 200
    kb_id = r.json()["data"]["id"]

    pdf_bytes = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    files = {"file": ("pg-test.pdf", pdf_bytes, "application/pdf")}
    r1 = pg_auth_client.post(
        f"/api/v1/documents?kb_id={kb_id}&on_conflict=create",
        files=files,
    )
    assert r1.status_code == 202
    payload = r1.json()["data"]
    job_id = payload["job_id"]
    document_id = payload["document_id"]

    r_job = pg_auth_client.get(f"/api/v1/index-jobs/{job_id}")
    assert r_job.status_code == 200
    data_job = r_job.json()["data"]
    assert data_job["id"] == job_id
    assert data_job["kb_id"] == kb_id

    r_latest = pg_auth_client.get(
        f"/api/v1/index-jobs/documents/{document_id}/index-job"
    )
    assert r_latest.status_code == 200
    assert r_latest.json()["data"]["id"] == job_id


def test_pg_user_row_persisted(pg_auth_client, pg_db_session):
    from sqlmodel import select

    from docpaws.domain.models.user import User

    users = list(pg_db_session.exec(select(User)).all())
    assert len(users) >= 1
