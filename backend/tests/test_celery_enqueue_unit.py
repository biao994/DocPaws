from __future__ import annotations


def test_enqueue_index_job_uses_celery_when_broker_configured(monkeypatch):
    """
    验证：当配置了 CELERY_BROKER_URL 时，IndexService.enqueue_index_job 会投递 Celery，
    而不是在 Web 进程内直接执行 run_index_job。
    """
    from docpaws.settings import settings
    from docpaws.usecases.index_service import IndexService

    # 开启 Celery broker 配置（避免走 BackgroundTasks fallback）
    monkeypatch.setattr(settings, "CELERY_BROKER_URL", "redis://127.0.0.1:6379/1", raising=False)

    called = {"apply_async": 0, "args": None, "task_id": None}

    class _FakeTask:
        def apply_async(self, *, args, task_id: str):
            called["apply_async"] += 1
            called["args"] = args
            called["task_id"] = task_id

    # 关键：patch 掉被 enqueue_index_job 动态 import 的 task
    import docpaws.infra.tasks.celery_tasks as celery_tasks

    monkeypatch.setattr(celery_tasks, "index_run_index_job", _FakeTask())

    # session 在此测试中不会被使用（仅验证投递逻辑）
    svc = IndexService(session=None)  # type: ignore[arg-type]

    job_id = "job_123"
    svc.enqueue_index_job(job_id=job_id, background_tasks=None)

    assert called["apply_async"] == 1
    assert called["args"] == [job_id]
    assert called["task_id"] == job_id

