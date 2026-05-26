"""
S3/MinIO 存储适配层：最小封装 upload/download/delete。

约束：
- 统一使用 path-style addressing（MinIO 常见部署需要）。
- 只暴露与业务层最小耦合的函数，便于后续替换云厂商。
"""

from __future__ import annotations

import os
import re
import tempfile
from typing import Iterable, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from docpaws.settings import settings


_S3_CONFIG = Config(s3={"addressing_style": "path"})


def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_INTERNAL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=_S3_CONFIG,
    )


def head_object(object_key: str) -> bool:
    """判断对象是否存在。"""
    s3 = _client()
    try:
        s3.head_object(Bucket=settings.S3_BUCKET, Key=object_key)
        return True
    except ClientError as e:
        code = str(e.response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


def head_meta(object_key: str) -> dict:
    """获取对象元信息（size/content_type/etag）。"""
    s3 = _client()
    r = s3.head_object(Bucket=settings.S3_BUCKET, Key=object_key)
    return {
        "content_type": r.get("ContentType"),
        "content_length": r.get("ContentLength"),
        "etag": (r.get("ETag") or "").strip('"'),
    }


def upload_file(local_path: str, object_key: str, content_type: Optional[str] = None) -> dict:
    """
    上传本地文件到对象存储。

    Returns:
        {etag, size}
    """
    s3 = _client()
    extra = {}
    if content_type:
        extra["ContentType"] = content_type
    s3.upload_file(local_path, settings.S3_BUCKET, object_key, ExtraArgs=extra or None)
    etag = ""
    try:
        r = s3.head_object(Bucket=settings.S3_BUCKET, Key=object_key)
        etag = (r.get("ETag") or "").strip('"')
    except Exception:
        pass
    return {"etag": etag, "size": os.path.getsize(local_path)}


def download_to_temp(object_key: str) -> str:
    """下载对象到临时文件，返回 temp_path（调用方负责删除）。"""
    s3 = _client()
    suffix = os.path.splitext(object_key)[1] or ".pdf"
    fd, temp_path = tempfile.mkstemp(prefix="docpaws_", suffix=suffix)
    os.close(fd)
    try:
        s3.download_file(settings.S3_BUCKET, object_key, temp_path)
        return temp_path
    except Exception:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
        raise


def delete_object(object_key: str) -> None:
    s3 = _client()
    s3.delete_object(Bucket=settings.S3_BUCKET, Key=object_key)


_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


def stream_get(
    object_key: str,
    *,
    range_header: str | None = None,
    chunk_size: int = 1024 * 1024,
) -> tuple[Iterable[bytes], dict]:
    """
    获取对象的流式内容（用于 API 转发）。

    Returns:
        (iterator, meta)
    """
    s3 = _client()
    kwargs = {"Bucket": settings.S3_BUCKET, "Key": object_key}
    if range_header:
        kwargs["Range"] = range_header
    resp = s3.get_object(**kwargs)
    body = resp["Body"]

    def _iter():
        while True:
            b = body.read(chunk_size)
            if not b:
                break
            yield b

    meta = {
        "content_type": resp.get("ContentType"),
        "content_length": resp.get("ContentLength"),
        # ContentRange: bytes start-end/total
        "content_range": resp.get("ContentRange"),
        "etag": (resp.get("ETag") or "").strip('"'),
    }
    return _iter(), meta

