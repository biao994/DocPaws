"""问答按用户限流（分钟次数 + 并发租约）。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from docpaws.settings import settings

logger = logging.getLogger(__name__)

_MINUTE_KEY_TTL_SECONDS = 70


class ChatRateLimitStoreUnavailable(Exception):
    """限流已开启但 Redis 未配置或操作失败（由 usecase 映射为对外错误）。"""


def _minute_bucket_key(user_id: str, *, now: datetime | None = None) -> str:
    ts = now or datetime.now(timezone.utc)
    return f"chat:rl:{user_id}:{ts.strftime('%Y%m%d%H%M')}"


def _concurrent_members_key(user_id: str) -> str:
    return f"chat:conc:{user_id}"


def _concurrent_lease_key(user_id: str, lease_id: str) -> str:
    return f"chat:conc:lease:{user_id}:{lease_id}"


def _as_str(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


def _require_redis(redis_client: Any | None) -> Any:
    if redis_client is None:
        raise ChatRateLimitStoreUnavailable("cache redis unavailable")
    return redis_client


def _purge_expired_concurrent_leases(user_id: str, redis_client: Any) -> None:
    """成员集里租约键已过期的项清掉，避免漏释放后名额永久虚占。"""
    members_key = _concurrent_members_key(user_id)
    members = redis_client.smembers(members_key) or set()
    for raw in list(members):
        lease_id = _as_str(raw)
        if not redis_client.exists(_concurrent_lease_key(user_id, lease_id)):
            redis_client.srem(members_key, raw)


def try_acquire_chat_minute_quota(user_id: str, redis_client: Any | None) -> bool:
    """
    碰模型前按 user_id 扣分钟次数。

    Returns:
        True  — 放行（开关关闭时直接放行）
        False — 已超分钟配额（调用方翻译为 RATE_LIMITED）

    Raises:
        ChatRateLimitStoreUnavailable — 开关开启但 Redis 不可用 / 操作失败
    """
    if not settings.CHAT_RATE_LIMIT_ENABLED:
        return True
    client = _require_redis(redis_client)
    try:
        key = _minute_bucket_key(user_id)
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, _MINUTE_KEY_TTL_SECONDS)
        return count <= settings.CHAT_RATE_LIMIT_PER_MINUTE
    except ChatRateLimitStoreUnavailable:
        raise
    except Exception as e:
        logger.warning("chat minute quota redis failed: %s", e)
        raise ChatRateLimitStoreUnavailable(str(e)) from e


def try_acquire_chat_concurrent_slot(
    user_id: str, lease_id: str, redis_client: Any | None
) -> bool:
    """
    占一个并发问答槽；成功时写入带 TTL 的租约。

    Returns:
        True  — 占槽成功（开关关闭时直接放行）
        False — 并发已满

    Raises:
        ChatRateLimitStoreUnavailable — 开关开启但 Redis 不可用 / 操作失败
    """
    if not settings.CHAT_RATE_LIMIT_ENABLED:
        return True
    client = _require_redis(redis_client)
    try:
        _purge_expired_concurrent_leases(user_id, client)
        members_key = _concurrent_members_key(user_id)
        if int(client.scard(members_key) or 0) >= settings.CHAT_CONCURRENT_LIMIT:
            return False

        ttl = settings.CHAT_CONCURRENT_TTL_SECONDS
        client.sadd(members_key, lease_id)
        client.set(_concurrent_lease_key(user_id, lease_id), b"1", ex=ttl)
        client.expire(members_key, ttl)
        return True
    except ChatRateLimitStoreUnavailable:
        raise
    except Exception as e:
        logger.warning("chat concurrent acquire redis failed: %s", e)
        raise ChatRateLimitStoreUnavailable(str(e)) from e


def release_chat_concurrent_slot(
    user_id: str, lease_id: str, redis_client: Any | None
) -> None:
    """释放并发槽；按租约幂等。Redis 故障时吞掉，避免影响主响应。"""
    if not settings.CHAT_RATE_LIMIT_ENABLED:
        return
    if redis_client is None:
        return

    try:
        lease_key = _concurrent_lease_key(user_id, lease_id)
        deleted = int(redis_client.delete(lease_key) or 0)
        members_key = _concurrent_members_key(user_id)
        redis_client.srem(members_key, lease_id)
        if deleted <= 0:
            return
        if int(redis_client.scard(members_key) or 0) <= 0:
            redis_client.delete(members_key)
    except Exception as e:
        logger.warning("chat concurrent release redis failed: %s", e)
