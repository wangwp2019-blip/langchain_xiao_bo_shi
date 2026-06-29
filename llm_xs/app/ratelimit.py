"""限流：按客户端维度的令牌桶（进程内）+ Redis 令牌桶（可选，fail-open）。"""

from __future__ import annotations

import logging
import math
import threading
import time

from .config import settings

logger = logging.getLogger(__name__)

# Redis Lua：原子令牌桶（跨实例一致）
_REDIS_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local ttl = math.ceil(capacity / rate * 60) + 10

local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])
if tokens == nil then
  tokens = capacity
  ts = now
end
local delta = math.max(0, now - ts)
tokens = math.min(capacity, tokens + delta * rate / 60.0)
local allowed = 0
if tokens >= 1.0 then
  tokens = tokens - 1.0
  allowed = 1
end
redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', key, ttl)
return allowed
"""


class _TokenBucket:
    def __init__(self, rate_per_min: int):
        self.capacity = float(max(rate_per_min, 1))
        self.refill = max(rate_per_min, 1) / 60.0
        self.tokens = self.capacity
        self.last = time.monotonic()

    def consume(self) -> bool:
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.refill)
        self.last = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    def retry_after_seconds(self) -> int:
        if self.tokens >= 1.0:
            return 0
        need = 1.0 - self.tokens
        return max(1, int(math.ceil(need / self.refill)))


class RateLimiter:
    """统一入口：``allow(client_id)`` / ``retry_after(client_id)``。"""

    def __init__(self, rate_per_min: int | None = None) -> None:
        self._rate = rate_per_min if rate_per_min is not None else settings.api_rate_limit_per_min
        self._buckets: dict[str, _TokenBucket] = {}
        self._lock = threading.Lock()
        self._redis = self._init_redis()
        self._lua = None
        if self._redis is not None:
            try:
                self._lua = self._redis.register_script(_REDIS_TOKEN_BUCKET_LUA)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis Lua 脚本注册失败，回退固定窗口：%s", exc)
                self._lua = None

    def _init_redis(self):
        if not settings.redis_url:
            return None
        try:
            import redis  # type: ignore

            client = redis.Redis.from_url(settings.redis_url, socket_timeout=1)
            client.ping()
            logger.info("限流使用 Redis 外部化：%s", settings.redis_url)
            return client
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis 不可用，回退进程内令牌桶：%s", exc)
            return None

    def allow(self, client_id: str) -> bool:
        if self._redis is not None:
            try:
                return self._allow_redis(client_id)
            except Exception as exc:  # noqa: BLE001
                if settings.ratelimit_fail_open:
                    logger.warning("Redis 限流异常，放行（fail-open）：%s", exc)
                    return True
                logger.error("Redis 限流异常，拒绝（fail-closed）：%s", exc)
                return False
        return self._allow_local(client_id)

    def retry_after(self, client_id: str) -> int:
        if self._redis is not None:
            # Redis 路径：按 refill 速率估算
            return max(1, int(math.ceil(60.0 / max(self._rate, 1))))
        with self._lock:
            bucket = self._buckets.get(client_id)
            if bucket is None:
                return 1
            return bucket.retry_after_seconds()

    def _allow_local(self, client_id: str) -> bool:
        with self._lock:
            if len(self._buckets) > settings.ratelimit_max_clients:
                drop = len(self._buckets) - settings.ratelimit_max_clients
                for key in list(self._buckets.keys())[:drop]:
                    self._buckets.pop(key, None)
            bucket = self._buckets.get(client_id)
            if bucket is None:
                bucket = _TokenBucket(self._rate)
                self._buckets[client_id] = bucket
            return bucket.consume()

    def _allow_redis(self, client_id: str) -> bool:
        if self._lua is not None:
            allowed = self._lua(
                keys=[f"kid:rl:tb:{client_id}"],
                args=[self._rate, self._rate, time.time()],
            )
            return int(allowed) == 1
        # 降级：固定窗口
        window = int(time.time() // 60)
        key = f"kid:rl:win:{client_id}:{window}"
        count = self._redis.incr(key)
        if count == 1:
            self._redis.expire(key, 90)
        return count <= self._rate


_limiter: RateLimiter | None = None
_chat_limiter: RateLimiter | None = None
_limiter_lock = threading.Lock()


def get_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        with _limiter_lock:
            if _limiter is None:
                _limiter = RateLimiter()
    return _limiter


def get_chat_limiter() -> RateLimiter:
    """聊天端点专用限流（通常比全局 API 更严）。"""
    global _chat_limiter
    if _chat_limiter is None:
        with _limiter_lock:
            if _chat_limiter is None:
                _chat_limiter = RateLimiter(rate_per_min=settings.chat_rate_limit_per_min)
    return _chat_limiter


def reset_limiter() -> None:
    """测试 / 配置热切换时重置单例。"""
    global _limiter, _chat_limiter
    with _limiter_lock:
        _limiter = None
        _chat_limiter = None
