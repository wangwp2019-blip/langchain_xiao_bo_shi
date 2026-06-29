"""出题会话存储后端：内存（单实例）/ Redis / MySQL（多 Worker 共享）。"""

from __future__ import annotations

import json
import logging
import secrets
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from ..config import settings
from ..domain import Grade, Question, Quiz, Subject

logger = logging.getLogger(__name__)

_PRINCIPAL_SEP = "\x1f"
_REDIS_KEY_PREFIX = "kid:quiz:session:"

# GET + 校验 principal + DEL 原子完成，principal 不匹配时不删除（防会话被恶意消耗）
_REDIS_CONSUME_LUA = """
local raw = redis.call('GET', KEYS[1])
if not raw then return nil end
local expected = ARGV[1]
local sep = string.find(raw, string.char(31))
if not sep then return nil end
local principal = string.sub(raw, 1, sep - 1)
if principal ~= expected then return nil end
redis.call('DEL', KEYS[1])
return string.sub(raw, sep + 1)
"""


def _ttl_seconds() -> int:
    return int(settings.quiz_session_ttl_seconds)


def _quiz_to_dict(quiz: Quiz) -> dict:
    return {
        "grade": quiz.grade.value,
        "subject": quiz.subject.value,
        "questions": [q.model_dump() for q in quiz.questions],
    }


def _quiz_from_dict(data: dict) -> Quiz:
    return Quiz(
        grade=Grade.parse(data["grade"]),
        subject=Subject.parse(data["subject"]),
        questions=[Question(**q) for q in data["questions"]],
    )


def _encode_payload(principal: str, quiz: Quiz) -> str:
    body = json.dumps({"quiz": _quiz_to_dict(quiz)}, ensure_ascii=False)
    return f"{principal}{_PRINCIPAL_SEP}{body}"


def _decode_payload(raw: str) -> tuple[str, dict] | None:
    if _PRINCIPAL_SEP not in raw:
        return None
    principal, body = raw.split(_PRINCIPAL_SEP, 1)
    try:
        return principal, json.loads(body)
    except json.JSONDecodeError:
        return None


class QuizSessionStore(ABC):
    @property
    @abstractmethod
    def backend_name(self) -> str: ...

    @abstractmethod
    def create(self, principal: str, quiz: Quiz) -> str: ...

    @abstractmethod
    def consume(self, session_id: str, principal: str) -> Quiz | None: ...

    @abstractmethod
    def ping(self) -> bool: ...

    @abstractmethod
    def clear_all(self) -> None: ...


@dataclass
class _MemEntry:
    principal: str
    quiz: Quiz
    expires_at: float


class MemoryQuizSessionStore(QuizSessionStore):
    @property
    def backend_name(self) -> str:
        return "memory"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, _MemEntry] = {}
        self._max = 5000

    def _sweep(self, now: float) -> None:
        expired = [k for k, v in self._sessions.items() if v.expires_at <= now]
        for k in expired:
            self._sessions.pop(k, None)
        if len(self._sessions) > self._max:
            drop = len(self._sessions) - self._max
            for k, _ in sorted(self._sessions.items(), key=lambda x: x[1].expires_at)[:drop]:
                self._sessions.pop(k, None)

    def create(self, principal: str, quiz: Quiz) -> str:
        session_id = secrets.token_urlsafe(24)
        now = time.time()
        with self._lock:
            self._sweep(now)
            self._sessions[session_id] = _MemEntry(
                principal=principal,
                quiz=quiz,
                expires_at=now + _ttl_seconds(),
            )
        return session_id

    def consume(self, session_id: str, principal: str) -> Quiz | None:
        with self._lock:
            entry = self._sessions.get(session_id)
            if not entry or entry.expires_at <= time.time():
                self._sessions.pop(session_id, None)
                return None
            if entry.principal != principal:
                return None
            self._sessions.pop(session_id, None)
            return entry.quiz

    def ping(self) -> bool:
        return True

    def clear_all(self) -> None:
        with self._lock:
            self._sessions.clear()


class RedisQuizSessionStore(QuizSessionStore):
    """Redis 共享会话（多 Gunicorn Worker / 多 Pod）。"""

    @property
    def backend_name(self) -> str:
        return "redis"

    def __init__(self, client: Any) -> None:
        self._client = client
        self._consume = self._client.register_script(_REDIS_CONSUME_LUA)
        self._client.ping()
        logger.info("出题会话使用 Redis 存储")

    @classmethod
    def from_url(cls, url: str) -> RedisQuizSessionStore:
        import redis

        client = redis.Redis.from_url(url, socket_timeout=2, decode_responses=True)
        return cls(client)

    def _key(self, session_id: str) -> str:
        return f"{_REDIS_KEY_PREFIX}{session_id}"

    def create(self, principal: str, quiz: Quiz) -> str:
        session_id = secrets.token_urlsafe(24)
        self._client.setex(
            self._key(session_id),
            _ttl_seconds(),
            _encode_payload(principal, quiz),
        )
        return session_id

    def consume(self, session_id: str, principal: str) -> Quiz | None:
        raw = self._consume(keys=[self._key(session_id)], args=[principal])
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        quiz_data = data.get("quiz")
        if not quiz_data:
            return None
        return _quiz_from_dict(quiz_data)

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception:
            return False

    def clear_all(self) -> None:
        for key in self._client.scan_iter(f"{_REDIS_KEY_PREFIX}*", count=200):
            self._client.delete(key)


class MySQLQuizSessionStore(QuizSessionStore):
    """MySQL 共享出题会话（多 Worker / 无 Redis 时的替代方案）。"""

    @property
    def backend_name(self) -> str:
        return "mysql"

    def __init__(self) -> None:
        from ..mysql import QuizSessionRepository

        self._repo = QuizSessionRepository()
        from ..mysql_db import ping_mysql

        if not ping_mysql():
            raise RuntimeError("MySQL 出题会话：连通性检查失败")
        logger.info("出题会话使用 MySQL 存储")

    def create(self, principal: str, quiz: Quiz) -> str:
        session_id = secrets.token_urlsafe(24)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=_ttl_seconds())
        self._repo.insert(
            session_id=session_id,
            principal=principal,
            quiz_json={"quiz": _quiz_to_dict(quiz)},
            expires_at=expires_at,
        )
        return session_id

    def consume(self, session_id: str, principal: str) -> Quiz | None:
        data = self._repo.consume(session_id, principal)
        if not data:
            return None
        quiz_data = data.get("quiz")
        if not quiz_data:
            return None
        return _quiz_from_dict(quiz_data)

    def ping(self) -> bool:
        try:
            from ..mysql_db import ping_mysql

            return ping_mysql()
        except Exception:
            return False

    def clear_all(self) -> None:
        self._repo.clear_all()


_store: QuizSessionStore | None = None
_store_lock = threading.Lock()


def _try_redis_store() -> QuizSessionStore | None:
    if not settings.redis_url:
        return None
    try:
        return RedisQuizSessionStore.from_url(settings.redis_url)
    except Exception as exc:
        logger.warning("Redis 出题会话不可用：%s", exc)
        return None


def _try_mysql_store() -> QuizSessionStore | None:
    if not settings.mysql_configured:
        return None
    try:
        return MySQLQuizSessionStore()
    except Exception as exc:
        logger.warning("MySQL 出题会话不可用：%s", exc)
        return None


def _create_store() -> QuizSessionStore:
    backend = (settings.quiz_session_backend or "auto").lower()
    if backend == "memory":
        logger.info("出题会话：memory（KIDS_QUIZ_SESSION_BACKEND=memory）")
        return MemoryQuizSessionStore()

    if backend == "redis":
        store = _try_redis_store()
        if store is not None:
            return store
        raise RuntimeError("KIDS_QUIZ_SESSION_BACKEND=redis 需要可用的 KIDS_REDIS_URL")

    if backend == "mysql":
        store = _try_mysql_store()
        if store is not None:
            return store
        raise RuntimeError(
            "KIDS_QUIZ_SESSION_BACKEND=mysql 需要可用的 KIDS_MYSQL_URL"
        )

    if backend == "auto":
        store = _try_redis_store()
        if store is not None:
            return store
        store = _try_mysql_store()
        if store is not None:
            return store
        logger.info("出题会话：memory（未配置 Redis/MySQL）")
        return MemoryQuizSessionStore()

    logger.warning("未知 KIDS_QUIZ_SESSION_BACKEND=%s，使用 memory", backend)
    return MemoryQuizSessionStore()


def get_quiz_session_store() -> QuizSessionStore:
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is not None:
            return _store
        _store = _create_store()
        return _store


def reset_quiz_session_store() -> None:
    global _store
    with _store_lock:
        if _store is not None:
            _store.clear_all()
        _store = None


def check_quiz_session_ready() -> dict[str, Any]:
    """health / ready 探针。"""
    backend = (settings.quiz_session_backend or "auto").lower()
    result: dict[str, Any] = {
        "backend_config": backend,
        "backend_active": "memory",
        "redis_url_configured": bool(settings.redis_url),
        "mysql_configured": settings.mysql_configured,
        "ready": True,
    }
    try:
        store = get_quiz_session_store()
        result["backend_active"] = store.backend_name
        result["ready"] = store.ping()
        if store.backend_name in ("redis", "mysql"):
            result["ttl_seconds"] = _ttl_seconds()
    except Exception as exc:  # noqa: BLE001
        result["ready"] = False
        result["error"] = str(exc)
    return result
