"""每用户每日在线大模型调用配额（防恶意刷量 / 控成本）。

- 配置 ``KIDS_LLM_DAILY_QUOTA_PER_USER``（0=不限制）后生效。
- 优先用 Redis（跨实例一致，按 UTC 自然日过期）；无 Redis 回退进程内计数。
- 仅对**在线大模型**路径计费；离线降级不消耗配额。
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

from .config import settings

logger = logging.getLogger(__name__)

_redis = None
_redis_init = False
_local_counts: dict[str, int] = {}
_local_day: str = ""
_lock = threading.Lock()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _seconds_until_utc_midnight() -> int:
    now = datetime.now(timezone.utc)
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
    secs = 86400 - (now - tomorrow).seconds
    return max(60, secs)


def _get_redis():
    global _redis, _redis_init
    if _redis_init:
        return _redis
    _redis_init = True
    if not settings.redis_url:
        _redis = None
        return None
    try:
        import redis  # type: ignore

        client = redis.Redis.from_url(settings.redis_url, socket_timeout=1)
        client.ping()
        _redis = client
    except Exception as exc:  # noqa: BLE001
        logger.warning("配额 Redis 不可用，回退进程内计数：%s", exc)
        _redis = None
    return _redis


def reset_quota_for_tests() -> None:
    """测试 / 配置热切换时重置状态。"""
    global _redis, _redis_init, _local_counts, _local_day
    with _lock:
        _redis = None
        _redis_init = False
        _local_counts = {}
        _local_day = ""


class QuotaExceeded(Exception):
    """超出每日配额。"""

    def __init__(self, limit: int, retry_after: int) -> None:
        super().__init__(f"daily quota {limit} exceeded")
        self.limit = limit
        self.retry_after = retry_after


def check_and_consume(principal: str) -> None:
    """消费一次配额；超限抛 ``QuotaExceeded``。配额=0 时直接放行。"""
    limit = settings.llm_daily_quota_per_user
    if limit <= 0:
        return

    day = _today()
    client = _get_redis()

    if client is not None:
        try:
            key = f"kid:quota:{day}:{principal}"
            count = client.incr(key)
            if count == 1:
                client.expire(key, _seconds_until_utc_midnight())
            if count > limit:
                raise QuotaExceeded(limit, _seconds_until_utc_midnight())
            return
        except QuotaExceeded:
            raise
        except Exception as exc:  # noqa: BLE001 - Redis 故障不应阻断服务
            logger.warning("配额 Redis 异常，回退进程内：%s", exc)

    global _local_counts, _local_day
    with _lock:
        if _local_day != day:
            _local_day = day
            _local_counts = {}
        used = _local_counts.get(principal, 0)
        if used >= limit:
            raise QuotaExceeded(limit, _seconds_until_utc_midnight())
        _local_counts[principal] = used + 1
