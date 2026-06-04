"""ensure_kb_index_job：僵尸 queued / 卡死 running 清理与再入队"""

import uuid
from datetime import datetime, timedelta

from sqlmodel import Session, select

from docpaws.domain.datetime_utils import utc_now
from docpaws.domain.models.index import IndexJob
from docpaws.infra.db.session import engine, create_db_and_tables
from docpaws.infra.repos.index_repo import (
    STALE_QUEUED_SECONDS,
    ensure_kb_index_job,
    is_stale_index_job,
    mark_index_job_stale_failed,
)


def test_is_stale_queued_when_progress_zero_and_old():
    job = IndexJob(
        kb_id="kb1",
        status="queued",
        progress=0,
        idempotency_key="k1",
        updated_at=utc_now() - timedelta(seconds=STALE_QUEUED_SECONDS + 1),
    )
    assert is_stale_index_job(job) is True


def test_non_stale_queued_returns_reenqueue():
    create_db_and_tables()
    kb_id = f"kb_stale_reenqueue_{uuid.uuid4().hex[:8]}"
    with Session(engine) as session:
        job = IndexJob(
            kb_id=kb_id,
            status="queued",
            progress=0,
            idempotency_key=f"kb:{kb_id}:old",
            updated_at=utc_now(),
        )
        session.add(job)
        session.commit()

        job_id, should_enqueue = ensure_kb_index_job(session, kb_id)
        session.commit()
        assert job_id == job.id
        assert should_enqueue is True


def test_stale_queued_marked_failed_and_new_job_enqueued():
    create_db_and_tables()
    kb_id = f"kb_stale_new_{uuid.uuid4().hex[:8]}"
    with Session(engine) as session:
        stale = IndexJob(
            kb_id=kb_id,
            status="queued",
            progress=0,
            idempotency_key=f"kb:{kb_id}:stale",
            updated_at=utc_now() - timedelta(seconds=STALE_QUEUED_SECONDS + 60),
        )
        session.add(stale)
        session.commit()
        stale_id = stale.id

        job_id, should_enqueue = ensure_kb_index_job(session, kb_id)
        session.commit()

        assert should_enqueue is True
        assert job_id != stale_id
        old = session.get(IndexJob, stale_id)
        assert old is not None
        assert old.status == "failed"
        assert "stale" in (old.error_message or "")

        new_job = session.get(IndexJob, job_id)
        assert new_job is not None
        assert new_job.status == "queued"


def test_mark_index_job_stale_failed():
    kb_id = f"kb_x_{uuid.uuid4().hex[:8]}"
    with Session(engine) as session:
        job = IndexJob(
            kb_id=kb_id,
            status="running",
            progress=50,
            idempotency_key=f"kb:{kb_id}:running",
        )
        session.add(job)
        session.flush()
        mark_index_job_stale_failed(session, job)
        session.commit()
        assert job.status == "failed"
        assert job.finished_at is not None
