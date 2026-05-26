from __future__ import annotations

from docpaws.infra.tasks.celery_app import celery_app
from docpaws.infra.tasks.index_worker import run_index_job


@celery_app.task(
    name="docpaws.index.run_index_job",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def index_run_index_job(self, job_id: str) -> None:
    run_index_job(job_id)

