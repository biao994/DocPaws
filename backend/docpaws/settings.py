"""
统一配置：env -> Settings

从环境变量加载所有配置项，集中管理。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# uvicorn 走 main.py 会 load_dotenv；Celery worker 不会，故在此加载 backend/.env
# 本文件路径：backend/docpaws/settings.py → backend = parent.parent
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_ROOT / ".env", override=False)


def _csv_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default).strip()
    return [x.strip() for x in raw.split(",") if x.strip()]


class Settings:
    """应用全局配置"""

    APP_NAME = "DocPaws"
    _BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/

    # Cookie Session（Starlette SessionMiddleware，签名的 session cookie，HttpOnly 由中间件设置）
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "dev-insecure-secret-change-me-use-long-random-string-min-32chars",
    )

    # CORS：带 Cookie 时不可使用 allow_origins=["*"]，需列出前端 Origin
    CORS_ORIGINS = _csv_env(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
    )

    SESSION_MAX_AGE_SECONDS = int(os.getenv("SESSION_MAX_AGE_SECONDS", str(14 * 24 * 3600)))

    # 生产环境建议 SESSION_HTTPS_ONLY=true
    SESSION_HTTPS_ONLY = os.getenv("SESSION_HTTPS_ONLY", "false").lower() in ("1", "true", "yes")

    # 服务端口
    PORT = int(os.getenv("PORT", "8000"))

    # 数据目录
    DATA_DIR =  _BASE_DIR / "backend"/"data"
    DB_PATH = str(DATA_DIR/ "docpaws.db")
    UPLOAD_DIR = str(DATA_DIR/ "uploads")
    # FAISS 在 Windows 下对中文路径兼容较差，索引目录固定到纯英文路径
    INDEX_DIR = os.getenv("INDEX_DIR", "C:/docpaws_data/w1/indexes")

    # 对象存储（S3/MinIO）
    # - INTERNAL：后端/worker 访问（容器内用 http://minio:9000；本机开发用 http://127.0.0.1:9000）
    # - EXTERNAL：将来做 presign 给前端用（本机开发也可同 INTERNAL）
    S3_ENDPOINT_INTERNAL = os.getenv("S3_ENDPOINT_INTERNAL", os.getenv("S3_ENDPOINT", "http://127.0.0.1:9000"))
    S3_ENDPOINT_EXTERNAL = os.getenv("S3_ENDPOINT_EXTERNAL", os.getenv("S3_ENDPOINT", "http://127.0.0.1:9000"))
    S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
    S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin123")
    S3_BUCKET = os.getenv("S3_BUCKET", "kb-files")
    S3_REGION = os.getenv("S3_REGION", "us-east-1")

    # Celery（与缓存建议分 Redis DB，如 /1 broker、/2 result）
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "")

    # Redis Cache（检索侧短 TTL 缓存）
    # 建议与 Celery broker/result 分实例或分端口（例如 cache:6379、queue:6380）
    CACHE_REDIS_URL = os.getenv("CACHE_REDIS_URL", "")
    CACHE_REDIS_PREFIX = os.getenv("CACHE_REDIS_PREFIX", "docpaws:retrieve:")
    RETRIEVAL_CACHE_TTL_SECONDS = int(os.getenv("RETRIEVAL_CACHE_TTL_SECONDS", "600"))
    # FAISS L2 距离上限（越小越相似）；<=0 表示不按距离过滤（仅空结果拒答）
    RETRIEVAL_MAX_DISTANCE = float(os.getenv("RETRIEVAL_MAX_DISTANCE", "1.2"))

    CACHE_REDIS_MAX_CONNECTIONS = int(os.getenv("CACHE_REDIS_MAX_CONNECTIONS", "50"))
    CACHE_REDIS_CONNECT_TIMEOUT_SECONDS = float(os.getenv("CACHE_REDIS_CONNECT_TIMEOUT_SECONDS", "2"))
    CACHE_REDIS_SOCKET_TIMEOUT_SECONDS = float(os.getenv("CACHE_REDIS_SOCKET_TIMEOUT_SECONDS", "2"))

    # PDF 卡片缩略图（首页 WebP，最长边像素）
    THUMBNAIL_MAX_WIDTH = int(os.getenv("THUMBNAIL_MAX_WIDTH", "400"))


settings = Settings()
