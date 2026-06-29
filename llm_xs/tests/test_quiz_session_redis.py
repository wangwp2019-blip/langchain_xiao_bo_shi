"""Redis 出题会话存储测试（fakeredis，无需真实 Redis 服务）。"""

from __future__ import annotations

import pytest

fakeredis = pytest.importorskip("fakeredis")

import app.config as cfg
from app.services import generate_quiz
from app.services.quiz_session_store import (
    MemoryQuizSessionStore,
    RedisQuizSessionStore,
    check_quiz_session_ready,
    get_quiz_session_store,
    reset_quiz_session_store,
)


@pytest.fixture()
def redis_store():
    client = fakeredis.FakeRedis(decode_responses=True)
    return RedisQuizSessionStore(client)


def test_redis_create_and_consume(redis_store):
    q = generate_quiz("三年级", "数学", 3, seed=5)
    sid = redis_store.create("uid:alice", q)
    got = redis_store.consume(sid, "uid:alice")
    assert got is not None
    assert len(got.questions) == 3
    assert redis_store.consume(sid, "uid:alice") is None


def test_redis_wrong_principal_does_not_burn_session(redis_store):
    """principal 不匹配时不应 DELETE，会话仍可被正确用户消费。"""
    q = generate_quiz("二年级", "语文", 2, seed=1)
    sid = redis_store.create("uid:owner", q)
    assert redis_store.consume(sid, "uid:attacker") is None
    got = redis_store.consume(sid, "uid:owner")
    assert got is not None
    assert len(got.questions) == 2


def test_redis_ttl_set(redis_store):
    q = generate_quiz("一年级", "数学", 1, seed=0)
    sid = redis_store.create("ip:test", q)
    ttl = redis_store._client.ttl(redis_store._key(sid))
    assert 0 < ttl <= cfg.settings.quiz_session_ttl_seconds


def test_get_store_uses_redis_when_configured(monkeypatch):
    reset_quiz_session_store()
    monkeypatch.setattr(cfg.settings, "quiz_session_backend", "redis")
    monkeypatch.setattr(cfg.settings, "redis_url", "redis://127.0.0.1:6379/0")

    class _FakeRedis:
        @classmethod
        def from_url(cls, url, **kwargs):
            return fakeredis.FakeRedis(decode_responses=True)

    import redis as redis_mod

    monkeypatch.setattr(redis_mod, "Redis", _FakeRedis)
    store = get_quiz_session_store()
    assert store.backend_name == "redis"
    reset_quiz_session_store()


def test_get_store_memory_when_backend_memory(monkeypatch):
    reset_quiz_session_store()
    monkeypatch.setattr(cfg.settings, "quiz_session_backend", "memory")
    store = get_quiz_session_store()
    assert isinstance(store, MemoryQuizSessionStore)
    reset_quiz_session_store()


def test_check_quiz_session_ready_memory(monkeypatch):
    reset_quiz_session_store()
    monkeypatch.setattr(cfg.settings, "quiz_session_backend", "memory")
    status = check_quiz_session_ready()
    assert status["backend_active"] == "memory"
    assert status["ready"] is True
    reset_quiz_session_store()
