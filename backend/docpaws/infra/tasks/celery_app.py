from __future__ import annotations

from celery import Celery

from docpaws.settings import settings


def _normalize_url(url: str) -> str:
    return (url or "").strip()


celery_app = Celery(
    "docpaws",
    broker=_normalize_url(settings.CELERY_BROKER_URL),
    backend=_normalize_url(settings.CELERY_RESULT_BACKEND) or None,
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
)

# 注册 @celery_app.task（import 副作用）
from docpaws.infra.tasks import celery_tasks  # noqa: E402,F401
