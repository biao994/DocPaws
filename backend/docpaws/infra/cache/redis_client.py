import logging
from threading import Lock

import redis

from docpaws.settings import settings

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None
_lock = Lock()


def get_cache_redis() -> redis.Redis | None:
    """
    获取缓存用 Redis 客户端（带连接池，单例）。

    - 若未配置 CACHE_REDIS_URL，则返回 None（业务侧应直接跳过缓存逻辑）
    - 连接异常时返回 None（不影响主链）
    """
    global _client

    url = (getattr(settings, "CACHE_REDIS_URL", "") or "").strip()
    if not url:
        return None

    if _client is not None:
        return _client

    with _lock:
        if _client is not None:
            return _client

        try:
            _client = redis.Redis.from_url(
                url,
                decode_responses=False,
                socket_connect_timeout=getattr(settings, "CACHE_REDIS_CONNECT_TIMEOUT_SECONDS", 2),
                socket_timeout=getattr(settings, "CACHE_REDIS_SOCKET_TIMEOUT_SECONDS", 2),
                max_connections=getattr(settings, "CACHE_REDIS_MAX_CONNECTIONS", 50),
                health_check_interval=30,
            )
            # 轻量探活：失败则禁用缓存（不抛到上层）
            _client.ping()
        except Exception as e:
            logger.warning(f"cache redis init failed: {e}")
            _client = None
            return None

    return _client

