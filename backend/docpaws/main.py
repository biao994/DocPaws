"""
启动入口：uvicorn docpaws.main:app
"""
from docpaws.app import app  # noqa: F401 — uvicorn 需要此模块级属性

import uvicorn

from docpaws.settings import settings

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def main():
    print(f"DocPaws Enterprise 启动中...")
    print(f"API 地址: http://localhost:{settings.PORT}")
    print(f"API 文档: http://localhost:{settings.PORT}/docs")

    uvicorn.run(
        "docpaws.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
