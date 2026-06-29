"""MySQL 出题会话存储测试（mock Repository，无需真实 MySQL）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import app.config as cfg
from app.services import generate_quiz
from app.services.quiz_session_store import (
    MySQLQuizSessionStore,
    get_quiz_session_store,
    reset_quiz_session_store,
)


class _FakeQuizSessionRepo:
    def __init__(self) -> None:
        self._rows: dict[str, dict] = {}

    def insert(self, *, session_id, principal, quiz_json, expires_at) -> int:
        self._rows[session_id] = {
            "principal": principal,
            "quiz_json": quiz_json,
            "expires_at": expires_at,
            "consumed_at": None,
        }
        return 1

    def consume(self, session_id: str, principal: str) -> dict | None:
        row = self._rows.get(session_id)
        if not row or row["consumed_at"] is not None:
            return None
        if row["expires_at"] <= datetime.now(timezone.utc):
            return None
        if row["principal"] != principal:
            return None
        row["consumed_at"] = datetime.now(timezone.utc)
        return row["quiz_json"]

    def clear_all(self) -> int:
        n = len(self._rows)
        self._rows.clear()
        return n


def test_mysql_create_and_consume(monkeypatch):
    fake = _FakeQuizSessionRepo()
    monkeypatch.setattr(
        "app.services.quiz_session_store.MySQLQuizSessionStore.__init__",
        lambda self: setattr(self, "_repo", fake) or None,
    )
    monkeypatch.setattr("app.mysql_db.ping_mysql", lambda: True)

    store = MySQLQuizSessionStore()
    q = generate_quiz("三年级", "数学", 3, seed=2)
    sid = store.create("uid:alice", q)
    got = store.consume(sid, "uid:alice")
    assert got is not None
    assert len(got.questions) == 3
    assert store.consume(sid, "uid:alice") is None


def test_mysql_wrong_principal_does_not_burn(monkeypatch):
    fake = _FakeQuizSessionRepo()
    monkeypatch.setattr(
        "app.services.quiz_session_store.MySQLQuizSessionStore.__init__",
        lambda self: setattr(self, "_repo", fake) or None,
    )
    monkeypatch.setattr("app.mysql_db.ping_mysql", lambda: True)

    store = MySQLQuizSessionStore()
    q = generate_quiz("二年级", "语文", 2, seed=1)
    sid = store.create("uid:owner", q)
    assert store.consume(sid, "uid:attacker") is None
    got = store.consume(sid, "uid:owner")
    assert got is not None


def test_auto_prefers_redis_over_mysql(monkeypatch):
    reset_quiz_session_store()
    monkeypatch.setattr(cfg.settings, "quiz_session_backend", "auto")
    monkeypatch.setattr(cfg.settings, "redis_url", "redis://127.0.0.1:6379/0")
    monkeypatch.setattr(cfg.settings, "mysql_url", "mysql://kid:kid@127.0.0.1/kid_assistant")

    class _FakeRedis:
        @classmethod
        def from_url(cls, url, **kwargs):
            import fakeredis

            return fakeredis.FakeRedis(decode_responses=True)

    import redis as redis_mod

    monkeypatch.setattr(redis_mod, "Redis", _FakeRedis)
    store = get_quiz_session_store()
    assert store.backend_name == "redis"
    reset_quiz_session_store()


def test_auto_falls_back_to_mysql(monkeypatch):
    reset_quiz_session_store()
    monkeypatch.setattr(cfg.settings, "quiz_session_backend", "auto")
    monkeypatch.setattr(cfg.settings, "redis_url", None)
    monkeypatch.setattr(cfg.settings, "mysql_url", "mysql://kid:kid@127.0.0.1/kid_assistant")

    fake = _FakeQuizSessionRepo()
    monkeypatch.setattr(
        "app.services.quiz_session_store.MySQLQuizSessionStore.__init__",
        lambda self: setattr(self, "_repo", fake) or None,
    )
    monkeypatch.setattr("app.mysql_db.ping_mysql", lambda: True)

    store = get_quiz_session_store()
    assert store.backend_name == "mysql"
    reset_quiz_session_store()


def test_get_store_mysql_backend(monkeypatch):
    reset_quiz_session_store()
    monkeypatch.setattr(cfg.settings, "quiz_session_backend", "mysql")
    monkeypatch.setattr(cfg.settings, "mysql_url", "mysql://kid:kid@127.0.0.1/kid_assistant")

    fake = _FakeQuizSessionRepo()
    monkeypatch.setattr(
        "app.services.quiz_session_store.MySQLQuizSessionStore.__init__",
        lambda self: setattr(self, "_repo", fake) or None,
    )
    monkeypatch.setattr("app.mysql_db.ping_mysql", lambda: True)

    store = get_quiz_session_store()
    assert store.backend_name == "mysql"
    reset_quiz_session_store()
