"""
索引任务编排

负责创建任务、触发后台执行、查询状态。
"""
from sqlmodel import Session

from docpaws.domain.models.index import IndexJob
from docpaws.infra.repos.index_repo import get_index_job_by_id, get_latest_index_job_by_document
from docpaws.api.schemas.index_jobs import IndexJobData


def _to_job_data(job: IndexJob) -> dict:
    return IndexJobData(
        id=job.id,
        kb_id=job.kb_id,
        status=job.status,
        progress=job.progress,
        error_message=job.error_message,
        diff_summary=job.diff_summary,
        created_at=job.created_at,
        updated_at=job.updated_at,
    ).model_dump()


def _get_job_impl(session: Session, job_id: str) -> dict | None:
    job = get_index_job_by_id(session, job_id)
    if not job:
        return None
    return _to_job_data(job)


def _get_document_latest_job_impl(session: Session, document_id: str) -> dict | None:
    job = get_latest_index_job_by_document(session, document_id)
    if not job:
        return None
    return _to_job_data(job)


class IndexService:
    def __init__(self, session: Session):
        self.session = session

    def get_job(self, *, job_id: str) -> dict | None:
        return _get_job_impl(self.session, job_id)

    def get_document_latest_job(self, *, document_id: str) -> dict | None:
        return _get_document_latest_job_impl(self.session, document_id)

    def enqueue_index_job(self, *, job_id: str, background_tasks: object | None = None) -> None:
        """
        入队索引任务。

        - 若配置了 CELERY_BROKER_URL，则优先投递到 Celery（Web 进程只投递）。
        - 若传入 background_tasks（FastAPI BackgroundTasks），则使用 add_task 异步执行。
        - 否则直接同步执行（适用于脚本/测试/worker 调用）。
        """
        from docpaws.infra.tasks.index_worker import run_index_job
        from docpaws.settings import settings

        if (settings.CELERY_BROKER_URL or "").strip():
            from docpaws.infra.tasks.celery_tasks import index_run_index_job

            index_run_index_job.apply_async(args=[job_id], task_id=job_id)
            return

        if background_tasks is not None and hasattr(background_tasks, "add_task"):
            # duck-typing: avoid binding usecases to FastAPI types
            background_tasks.add_task(run_index_job, job_id)  # type: ignore[attr-defined]
            return
        run_index_job(job_id)
