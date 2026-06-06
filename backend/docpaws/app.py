"""
App 工厂：中间件 / 异常处理 / 路由注册 / 静态挂载 / 启动事件

只做框架组装，不写业务逻辑。
"""
import logging
import os
import uuid

from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
# from fastapi.staticfiles import StaticFiles   # 静态挂载时再启用（需 aiofiles）

from docpaws.settings import settings
from docpaws.infra.db.session import create_db_and_tables
from fastapi.responses import JSONResponse

from docpaws.api.response import ErrorCode, error, get_status_code
from docpaws.errors import AppError

logger = logging.getLogger("docpaws")


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME)

    # ── Cookie Session（内层）：先 add 的更接近应用，后 add 的在外层 ──
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        session_cookie="session",
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        same_site="lax",
        https_only=settings.SESSION_HTTPS_ONLY,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.CORS_ORIGINS),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "X-Request-ID"],
    )

    # ── 请求 ID 中间件 ────────────────────────────────────
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:16]}"
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    # ── 启动事件 ──────────────────────────────────────────
    @app.on_event("startup")
    def _startup():
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        os.makedirs(settings.INDEX_DIR, exist_ok=True)
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        create_db_and_tables()
        logger.info("DocPaws Enterprise started")

    # ── 健康检查 & 根路由 ───────────────────────────────
    @app.get("/healthz")
    def healthz():
        db = "sqlite" if settings.is_sqlite else "postgresql"
        return {"status": "ok", "name": settings.APP_NAME, "version": "enterprise-v2", "db": db}

    @app.get("/")
    def root():
        return {
            "name": settings.APP_NAME,
            "version": "enterprise-v2",
            "status": "running",
            "docs": "/docs",
            "health": "/healthz",
        }

    # ── 统一异常处理 ──────────────────────────────────────
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        rid = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=exc.status_code,
            content=error(
                exc.error_code,
                message=exc.message,
                user_hint=exc.user_hint,
                request_id=rid,
                details=exc.details,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(request: Request, exc: RequestValidationError):
        rid = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=get_status_code(ErrorCode.VALIDATION_ERROR),
            content=error(
                ErrorCode.VALIDATION_ERROR,
                message="请求参数不合法",
                request_id=rid,
                details={"errors": exc.errors()},
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """
        HTTP 层异常兜底（不承载业务错误）。
        业务错误应统一抛 AppError，由 app_error_handler 输出标准错误响应。
        """
        rid = getattr(request.state, "request_id", "unknown")
        code = ErrorCode.VALIDATION_ERROR if 400 <= exc.status_code < 500 else ErrorCode.INTERNAL_ERROR
        return JSONResponse(
            status_code=exc.status_code,
            content=error(code, message=str(exc.detail), request_id=rid),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        rid = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=get_status_code(ErrorCode.INTERNAL_ERROR),
            content=error(ErrorCode.INTERNAL_ERROR, message=str(exc), request_id=rid),
        )

    # ── 注册路由（按资源拆分）────────────────────────────
    from docpaws.api.routers import auth, users, kb, documents, folders, index_jobs, chat, conversations, feedback

    app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
    app.include_router(users.router, prefix="/api/v1", tags=["users"])

    app.include_router(kb.router, prefix="/api/v1", tags=["knowledge-bases"])
    app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
    app.include_router(folders.router, prefix="/api/v1", tags=["folders"])
    app.include_router(index_jobs.router, prefix="/api/v1", tags=["index-jobs"])
    app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
    app.include_router(conversations.router, prefix="/api/v1", tags=["conversations"])
    app.include_router(feedback.router, prefix="/api/v1", tags=["feedback"])

    return app


app = create_app()
