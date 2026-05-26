from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AppError(Exception):
    """业务异常（可预期）：由 usecases/domain 主动抛出，API 层统一转换为标准错误响应。"""

    error_code: str
    message: str
    status_code: int = 400
    user_hint: str | None = None
    details: dict[str, Any] | None = None

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.error_code}: {self.message}"

