"""
文档管理路由：列表/详情/删除/上传
"""
import json

from botocore.exceptions import ClientError
from sqlmodel import Session
from fastapi import APIRouter, Request, Depends, Query, File, UploadFile, BackgroundTasks, status, Form
from fastapi.responses import StreamingResponse

from docpaws.api.authz import require_document_readable, require_kb_owned
from docpaws.api.deps import get_document_service, get_index_service, get_current_user, DependsSession
from docpaws.domain.models.user import User
from docpaws.api.response import success, get_status_code, ErrorCode
from docpaws.api.schemas.documents import DocumentUpdateRequest
from docpaws.usecases.document_service import DocumentService
from docpaws.usecases.index_service import IndexService
from docpaws.errors import AppError
from docpaws.infra.storage.s3_minio import head_meta, stream_get
from docpaws.usecases.thumbnail_service import THUMBNAIL_CACHE_CONTROL

router = APIRouter(dependencies=[Depends(get_current_user)])


def _is_object_not_found_error(err: Exception) -> bool:
    if not isinstance(err, ClientError):
        return False
    code = str(err.response.get("Error", {}).get("Code", ""))
    return code in {"404", "NoSuchKey", "NotFound"}


def _raise_file_not_found(*, object_key: str, document_id: str) -> None:
    raise AppError(
        error_code=ErrorCode.FILE_NOT_FOUND,
        message="file not found",
        status_code=get_status_code(ErrorCode.FILE_NOT_FOUND),
        details={"document_id": document_id, "object_key": object_key},
    )


@router.get("/knowledge-bases/{kb_id}/documents")
def api_list_documents(
    request: Request,
    kb_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = DependsSession,
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: DocumentService = Depends(get_document_service),
    folder_path: str | None = Query(None),
    folder_id: str | None = Query(None),
):
    require_kb_owned(session, kb_id, current_user.id)

    items, total = svc.list_documents(
        kb_id=kb_id,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
        folder_path_filter=folder_path,
        folder_id_filter=folder_id,
    )
    return success(data={
        "items": items,
        "page": page, "page_size": page_size, "total": total,
    }, request_id=request.state.request_id)


@router.get("/documents/{document_id}")
def api_get_document(
    request: Request,
    document_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = DependsSession,
    svc: DocumentService = Depends(get_document_service),
):
    require_document_readable(session, document_id, current_user.id)

    data = svc.get_document(document_id=document_id)
    return success(data=data, request_id=request.state.request_id)


@router.get("/documents/{document_id}/file")
def api_get_document_file(
    request: Request,
    document_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = DependsSession,
    svc: DocumentService = Depends(get_document_service),
):
    """获取文档原始文件（用于 PDF 预览）"""
    require_document_readable(session, document_id, current_user.id)

    object_key, filename = svc.get_document_file(document_id=document_id)
    range_req = request.headers.get("range")
    try:
        base_meta = head_meta(object_key)
    except Exception as e:
        if _is_object_not_found_error(e):
            _raise_file_not_found(object_key=object_key, document_id=document_id)
        raise
    total = base_meta.get("content_length")
    if total is None or int(total) <= 0:
        _raise_file_not_found(object_key=object_key, document_id=document_id)
    ctype = base_meta.get("content_type") or "application/pdf"

    headers = {
        "Content-Disposition": "inline",
        "Content-Type": ctype,
        "Accept-Ranges": "bytes",
    }
    if base_meta.get("etag"):
        headers["ETag"] = base_meta["etag"]

    # 无 Range：直接整文件返回（200）
    if not range_req:
        try:
            it, meta = stream_get(object_key)
        except Exception as e:
            if _is_object_not_found_error(e):
                _raise_file_not_found(object_key=object_key, document_id=document_id)
            raise
        if meta.get("content_length") is not None:
            headers["Content-Length"] = str(meta["content_length"])
        return StreamingResponse(it, media_type=ctype, headers=headers)

    # 仅支持单段 Range（bytes=start-end / bytes=start- / bytes=-suffix）
    if not range_req.startswith("bytes=") or "," in range_req or total is None:
        # 无法满足 Range（不支持多段，或无法得知总长度）
        if total is not None:
            headers["Content-Range"] = f"bytes */{total}"
        return StreamingResponse(iter(()), status_code=416, headers=headers)

    spec = range_req[len("bytes="):].strip()
    start_s, end_s = (spec.split("-", 1) + [""])[:2]

    try:
        if start_s == "" and end_s == "":
            raise ValueError("empty range")
        if start_s == "":  # suffix: -N
            suffix = int(end_s)
            if suffix <= 0:
                raise ValueError("invalid suffix")
            if suffix > total:
                suffix = total
            start = total - suffix
            end = total - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s != "" else total - 1
            if start < 0:
                raise ValueError("negative start")
            if end < start:
                raise ValueError("end < start")
            if start >= total:
                raise ValueError("start >= total")
            if end >= total:
                end = total - 1
    except Exception:
        headers["Content-Range"] = f"bytes */{total}"
        return StreamingResponse(iter(()), status_code=416, headers=headers)

    range_header = f"bytes={start}-{end}"
    try:
        it, meta = stream_get(object_key, range_header=range_header)
    except Exception as e:
        if _is_object_not_found_error(e):
            _raise_file_not_found(object_key=object_key, document_id=document_id)
        raise

    headers["Content-Range"] = f"bytes {start}-{end}/{total}"
    headers["Content-Length"] = str(end - start + 1)
    return StreamingResponse(it, media_type=ctype, headers=headers, status_code=206)


@router.get("/documents/{document_id}/thumbnail")
def api_get_document_thumbnail(
    request: Request,
    document_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = DependsSession,
    svc: DocumentService = Depends(get_document_service),
):
    """获取文档首页缩略图（WebP）"""
    require_document_readable(session, document_id, current_user.id)

    object_key = svc.get_document_thumbnail(document_id=document_id)
    try:
        base_meta = head_meta(object_key)
    except Exception as e:
        if _is_object_not_found_error(e):
            _raise_file_not_found(object_key=object_key, document_id=document_id)
        raise

    try:
        it, meta = stream_get(object_key)
    except Exception as e:
        if _is_object_not_found_error(e):
            _raise_file_not_found(object_key=object_key, document_id=document_id)
        raise

    headers = {
        "Content-Type": base_meta.get("content_type") or "image/webp",
        "Cache-Control": THUMBNAIL_CACHE_CONTROL,
    }
    if base_meta.get("content_length") is not None:
        headers["Content-Length"] = str(base_meta["content_length"])
    if base_meta.get("etag"):
        headers["ETag"] = base_meta["etag"]
    if meta.get("content_length") is not None:
        headers["Content-Length"] = str(meta["content_length"])

    return StreamingResponse(it, media_type=headers["Content-Type"], headers=headers)


@router.patch("/documents/{document_id}")
def api_update_document(
    request: Request,
    document_id: str,
    req: DocumentUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = DependsSession,
    svc: DocumentService = Depends(get_document_service),
):
    require_document_readable(session, document_id, current_user.id)
    data = svc.update_document(document_id=document_id, title=req.title)
    return success(data=data, request_id=request.state.request_id)


@router.delete("/documents/{document_id}")
def api_delete_document(
    request: Request,
    document_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = DependsSession,
    svc: DocumentService = Depends(get_document_service),
    index_svc: IndexService = Depends(get_index_service),
):
    require_document_readable(session, document_id, current_user.id)

    data = svc.delete_document(document_id=document_id)
    if data.get("should_enqueue") and data.get("job_id"):
        index_svc.enqueue_index_job(job_id=data["job_id"], background_tasks=background_tasks)
    return success(data=data, request_id=request.state.request_id)


@router.post("/documents", status_code=status.HTTP_202_ACCEPTED)
async def api_upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    kb_id: str = Query(...),
    idempotency_key: str | None = Query(None),
    folder_path: str | None = Query(None),
    folder_id: str | None = Query(None),
    on_conflict: str = Query(
        "create",
        description="重名策略：create 重名返回409 | replace 覆盖已有文档 | auto_rename 自动加时间戳后新建",
    ),
    replace_document_id: str | None = Query(None),
    file: UploadFile = File(..., description="PDF 文件"),
    current_user: User = Depends(get_current_user),
    session: Session = DependsSession,
    svc: DocumentService = Depends(get_document_service),
    index_svc: IndexService = Depends(get_index_service),
):
    """上传文档（返回 202）"""
    request_id = request.state.request_id

    require_kb_owned(session, kb_id, current_user.id)

    # 参数校验
    raw_filename = (file.filename or "").strip()
    if not raw_filename:
        raise AppError(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="文件名不能为空",
            status_code=get_status_code(ErrorCode.VALIDATION_ERROR),
        )

    is_pdf = raw_filename.lower().endswith(".pdf") or (file.content_type or "").lower() in {"application/pdf", "application/x-pdf"}
    if not is_pdf:
        raise AppError(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="仅支持 PDF 文件",
            status_code=get_status_code(ErrorCode.VALIDATION_ERROR),
        )

    allowed_modes = {"create", "replace", "auto_rename"}
    if on_conflict not in allowed_modes:
        raise AppError(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="不支持此操作",
            status_code=get_status_code(ErrorCode.VALIDATION_ERROR),
        )

    # 调用业务层
    try:
        result = await svc.upload_document(
            file=file,
            raw_filename=raw_filename,
            kb_id=kb_id,
            user_id=current_user.id,
            folder_path=folder_path,
            folder_id=folder_id,
            idempotency_key=idempotency_key,
            on_conflict=on_conflict,
            replace_document_id=replace_document_id,
        )
    finally:
        try:
            await file.close()
        except Exception:
            pass

    # 触发后台任务（入队逻辑统一由 IndexService 承担；复用 KB 任务时不再重复入队）
    if result.get("should_enqueue", True):
        index_svc.enqueue_index_job(job_id=result["job_id"], background_tasks=background_tasks)

    return success(data=result, request_id=request_id)


@router.post("/knowledge-bases/{kb_id}/documents/batch", status_code=status.HTTP_202_ACCEPTED)
async def api_upload_documents_batch(
    request: Request,
    background_tasks: BackgroundTasks,
    kb_id: str,
    files: list[UploadFile] = File(..., description="多个 PDF，字段名 files 可重复"),
    on_conflict: str = Query(
        "create",
        description="create 重名返回409 | auto_rename 自动加时间戳",
    ),
    idempotency_key: str | None = Query(None),
    folder_path: str | None = Query(None, description="与单文件上传相同；无 relative_paths 时所有文件共用此目录"),
    folder_id: str | None = Query(None, description="目标文件夹 id；与 folder_path 二选一，优先 folder_id"),
    relative_paths: str | None = Form(
        None,
        description='可选 JSON 数组，与 files 等长，如 ["dir/a.pdf","b.pdf"]，用于文件夹相对路径',
    ),
    current_user: User = Depends(get_current_user),
    session: Session = DependsSession,
    svc: DocumentService = Depends(get_document_service),
    index_svc: IndexService = Depends(get_index_service),
):
    """批量上传 PDF：一次请求内落库多条文档，只创建/复用一条 KB 级索引任务。"""
    request_id = request.state.request_id
    require_kb_owned(session, kb_id, current_user.id)

    if on_conflict not in {"create", "auto_rename"}:
        raise AppError(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="批量上传仅支持 create 或 auto_rename",
            status_code=get_status_code(ErrorCode.VALIDATION_ERROR),
        )

    rel_list: list[str] | None = None
    if relative_paths is not None and relative_paths.strip():
        try:
            parsed = json.loads(relative_paths)
        except json.JSONDecodeError:
            raise AppError(
                error_code=ErrorCode.VALIDATION_ERROR,
                message="relative_paths 不是合法 JSON",
                status_code=get_status_code(ErrorCode.VALIDATION_ERROR),
            )
        if not isinstance(parsed, list) or any(not isinstance(x, str) for x in parsed):
            raise AppError(
                error_code=ErrorCode.VALIDATION_ERROR,
                message="relative_paths 须为字符串数组",
                status_code=get_status_code(ErrorCode.VALIDATION_ERROR),
            )
        rel_list = parsed

    try:
        result = await svc.upload_documents_batch(
            files=files,
            kb_id=kb_id,
            user_id=current_user.id,
            folder_path=folder_path,
            folder_id=folder_id,
            relative_paths=rel_list,
            on_conflict=on_conflict,
            idempotency_key=idempotency_key,
        )
    finally:
        for f in files:
            try:
                await f.close()
            except Exception:
                pass

    if result.get("should_enqueue", True):
        index_svc.enqueue_index_job(job_id=result["job_id"], background_tasks=background_tasks)

    return success(data=result, request_id=request_id)
