"""问答按用户次数限流（Redis 固定窗）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from docpaws.settings import settings

_MINUTE_KEY_TTL_SECONDS = 70


def _minute_bucket_key(user_id: str, *, now: datetime | None = None) -> str:
    ts = now or datetime.now(timezone.utc)
    return f"chat:rl:{user_id}:{ts.strftime('%Y%m%d%H%M')}"


def try_acquire_chat_minute_quota(user_id: str, redis_client: Any | None) -> bool:
    """
    碰模型前按 user_id 扣分钟次数。

    Returns:
        True  — 放行（含开关关闭 / 无 Redis 客户端时本刀直接放行）
        False — 已超分钟配额（调用方翻译为 RATE_LIMITED）

    本刀不处理并发闸 / Redis 故障 fail-closed。
    """
    if not settings.CHAT_RATE_LIMIT_ENABLED:
        return True
    if redis_client is None:
        return True

    key = _minute_bucket_key(user_id)
    count = int(redis_client.incr(key))
    if count == 1:
        redis_client.expire(key, _MINUTE_KEY_TTL_SECONDS)
    return count <= settings.CHAT_RATE_LIMIT_PER_MINUTE
