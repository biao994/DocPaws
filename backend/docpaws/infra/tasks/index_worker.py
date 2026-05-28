"""
索引任务执行器

后台任务执行器（可替换 Celery/RQ/Arq）。
负责：PDF 解析 -> 分块 -> 向量构建 -> 产物记录。
仅支持 KB 级任务：始终对该 kb_id 做 manifest diff、增量 chunk + FAISS 全量重建。
"""
import os
import traceback

from sqlmodel import Session, select

from docpaws.config import get_default_config
from docpaws.infra.parsers.pdf_loader import load_pdf_documents
from docpaws.infra.storage.s3_minio import download_to_temp
from docpaws.infra.vectorstore.faiss_manager import VectorStoreManager
from docpaws.infra.db.session import engine
from docpaws.domain.models.document import Document, Chunk
from docpaws.infra.repos.document_repo import (
    delete_chunks_by_document_id,
    delete_chunks_for_document_ids,
    fail_documents_in_indexing,
    has_any_chunk,
    resolve_document_file,
    set_document_status,
)
from docpaws.infra.repos.index_repo import (
    create_kb_index_artifact,
    deactivate_active_artifacts,
    get_next_artifact_version,
    mark_index_job_running,
    merge_job_parse_failures,
    record_kb_diff_on_job,
    update_index_job,
)
from docpaws.settings import settings


def run_index_job(job_id: str) -> None:
    """执行 KB 级索引任务（Celery / BackgroundTasks 入口）。

    标 running 后委托 ``_execute_kb_index_pipeline``：manifest diff → 按变更增删/重切 chunk
    → 全库 FAISS 重建 → 写 artifact/manifest；失败时将该 KB 下 indexing 文档标 failed。
    """
    with Session(engine) as session:
        kb_id = mark_index_job_running(session, job_id)
        if not kb_id:
            return
        session.commit()

    try:
        _execute_kb_index_pipeline(job_id, kb_id)
    except Exception as e:
        if isinstance(e, ValueError):
            err = f"{type(e).__name__}: {e}"
        else:
            err = f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=5)}"
        with Session(engine) as session:
            fail_documents_in_indexing(session, kb_id)
            update_index_job(session, job_id, status="failed", error_message=err[:1000])
            session.commit()


def _execute_kb_index_pipeline(job_id: str, kb_id: str) -> None:
    """KB 级增量索引主流程：diff → 删/重切 chunk → 全量 FAISS 重建 → 落 artifact。"""
    # 1. 对比当前 manifest 与库内文档，得到 added/modified/deleted，并写入 job 的 diff_summary字段
    with Session(engine) as session:
        diff, new_map = record_kb_diff_on_job(session, job_id, kb_id)
        session.commit()

    _touch_job_progress(job_id, 20)

    # 2. 已删除文档：直接清掉其 chunk（向量索引稍后全量重建，此处只维护 DB）
    with Session(engine) as session:
        delete_chunks_for_document_ids(session, diff["deleted"])
        session.commit()

    # 3. 变更/新增文档：先删旧 chunk，再解析 PDF 并写入新 chunk；解析失败记入 failed_parse
    failed_parse: list[str] = []
    for doc_id in diff["modified"]:
        with Session(engine) as session:
            delete_chunks_by_document_id(session, doc_id)
            session.commit()
    _chunk_documents_for_index(diff["modified"], failed_parse)
    _chunk_documents_for_index(diff["added"], failed_parse)

    with Session(engine) as session:
        merge_job_parse_failures(session, job_id, failed_parse)
        session.commit()

    _touch_job_progress(job_id, 50)

    # 4. 若 KB 下已无任何 chunk（例如全部删除或解析均失败），停用旧 artifact 后直接成功结束
    with Session(engine) as session:
        if not has_any_chunk(session, kb_id):
            deactivate_active_artifacts(session, kb_id)
            update_index_job(session, job_id, status="succeeded")
            session.commit()
            return
        next_version = get_next_artifact_version(session, kb_id)
        session.commit()

    # 5. 基于当前 KB 全部 chunk 全量重建 FAISS，写入新版本目录
    index_path = _index_path_for_kb(kb_id, next_version)
    os.makedirs(index_path, exist_ok=True)

    _build_vector_index(kb_id, index_path)
    _touch_job_progress(job_id, 80)

    # 6. 登记新 artifact（含 manifest content_hash），切换为 active，并标记任务成功
    with Session(engine) as session:
        create_kb_index_artifact(
            session,
            kb_id,
            next_version,
            index_path,
            job_id,
            new_content_hashes=new_map,
        )
        update_index_job(session, job_id, status="succeeded")
        session.commit()


def _touch_job_progress(job_id: str, progress: int) -> None:
    with Session(engine) as session:
        update_index_job(session, job_id, progress=progress)
        session.commit()


def _chunk_documents_for_index(document_ids: list[str], failed_parse: list[str]) -> None:
    for doc_id in document_ids:
        with Session(engine) as session:
            set_document_status(session, doc_id, "indexing")
            session.commit()
        try:
            with Session(engine) as session:
                object_key, filename = resolve_document_file(session, doc_id)
            n = _parse_and_chunk_document(doc_id, object_key, filename)
        except Exception:
            n = 0
        if n == 0:
            with Session(engine) as session:
                set_document_status(session, doc_id, "failed")
                session.commit()
            failed_parse.append(doc_id)


def _index_path_for_kb(kb_id: str, version: int) -> str:
    return os.path.join(settings.INDEX_DIR, kb_id, f"v{version}")


def _parse_and_chunk_document(document_id: str, object_key: str, original_filename: str) -> int:
    """解析 PDF 并分块，返回写入的 chunk 数量。"""
    cfg = get_default_config()
    vsm = VectorStoreManager(cfg)

    temp_pdf_path = download_to_temp(object_key)
    try:
        if os.path.getsize(temp_pdf_path) <= 0:
            raise ValueError(f"empty pdf after download: {object_key}")
        docs = load_pdf_documents(temp_pdf_path, source_name=original_filename)
        chunks = vsm.split_documents(docs)
    finally:
        try:
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
        except Exception:
            pass

    chunks_to_create = []
    for doc in chunks:
        chunks_to_create.append(
            Chunk(
                document_id=document_id,
                content=doc.page_content,
                page_no=doc.metadata.get("page"),
            )
        )

    if not chunks_to_create:
        return 0

    with Session(engine) as session:
        if not session.get(Document, document_id):
            raise RuntimeError(f"document not found before chunk insert: {document_id}")
        session.add_all(chunks_to_create)
        session.commit()
    return len(chunks_to_create)


def _build_vector_index(kb_id: str, index_path: str) -> None:
    """全量重建知识库向量索引。"""
    from langchain_core.documents import Document as LCDocument

    cfg = get_default_config()
    all_docs_for_index = []

    with Session(engine) as session:
        rows = session.exec(
            select(Chunk, Document)
            .join(Document, Document.id == Chunk.document_id)
            .where(Document.kb_id == kb_id)
            .order_by(Document.created_at.asc(), Chunk.id.asc())
        ).all()

        print(f"[索引] 全量索引：知识库 {kb_id} 共 {len(rows)} 个 chunks")

        for chunk, doc in rows:
            doc_title = doc.title or "未命名文档"
            all_docs_for_index.append(
                LCDocument(
                    page_content=chunk.content,
                    metadata={
                        "chunk_id": chunk.id,
                        "document_id": doc.id,
                        "page": chunk.page_no,
                        "source": doc_title,
                    },
                )
            )

    print(f"[索引] 总共收集到 {len(all_docs_for_index)} 个 chunks")

    if not all_docs_for_index:
        raise ValueError("没有可索引的文档内容")

    VectorStoreManager(cfg).create_vector_store(all_docs_for_index, save_path=index_path)
