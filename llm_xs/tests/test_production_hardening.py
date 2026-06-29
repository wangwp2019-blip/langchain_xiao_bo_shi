"""生产级：出题会话与上线门禁测试。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.config as cfg
from app.ratelimit import reset_limiter
from app.security import derive_user_id
from app.services import generate_quiz
from app.services.quiz_session import clear_sessions_for_tests, create_session


def test_quiz_session_hides_answers(client):
    clear_sessions_for_tests()
    resp = client.post(
        "/api/quiz",
        json={"grade": "二年级", "subject": "语文", "count": 3, "seed": 1},
    ).json()
    assert "session_id" in resp
    assert "quiz" not in resp
    assert "answer" not in str(resp)


def test_grade_rejects_fake_session(client):
    r = client.post(
        "/api/grade",
        json={"session_id": "invalid-session-id", "answers": {"1": "x"}},
    )
    assert r.status_code == 400


def test_grade_session_principal_isolation(client):
    clear_sessions_for_tests()
    q = generate_quiz("三年级", "数学", 2, seed=99)
    sid = create_session("uid:other-principal", q)
    r = client.post(
        "/api/grade",
        json={"session_id": sid, "answers": {"1": "1", "2": "2"}},
    )
    assert r.status_code == 400


def test_ingest_requires_token_when_configured(client, monkeypatch):
    monkeypatch.setattr(cfg.settings, "ingest_token", "ingest-secret")
    r = client.post("/api/ingest")
    assert r.status_code == 403
    ok = client.post("/api/ingest", headers={"X-Ingest-Token": "ingest-secret"})
    assert ok.status_code == 200


def test_quiz_session_roundtrip():
    from app.services import generate_quiz
    from app.services.quiz_session import clear_sessions_for_tests, consume_session, create_session

    clear_sessions_for_tests()
    q = generate_quiz("二年级", "数学", 3, seed=1)
    sid = create_session("ip:test", q)
    got = consume_session(sid, "ip:test")
    assert got is not None
    assert len(got.questions) == 3
    assert consume_session(sid, "ip:test") is None


def test_chat_limiter_separate_rate():
    from app.ratelimit import get_chat_limiter, get_limiter, reset_limiter

    reset_limiter()
    assert get_chat_limiter()._rate == cfg.settings.chat_rate_limit_per_min
    assert get_limiter()._rate == cfg.settings.api_rate_limit_per_min


def test_privacy_export(client):
    import uuid

    from app.memory_admin import remember_fact

    sub = f"privacy-{uuid.uuid4().hex[:8]}"
    uid = derive_user_id("ip:testclient", sub)
    remember_fact(uid, "测试导出")
    data = client.get("/api/privacy/export", params={"sub": sub}).json()
    assert data["user_id"] == uid
    assert data["memory"]["facts"]


def test_production_auth_gate(monkeypatch):
    monkeypatch.setenv("KIDS_REQUIRE_AUTH", "true")
    cfg.settings.require_auth = True
    cfg.settings.api_keys = None
    cfg.settings.jwt_secret = None
    reset_limiter()
    from app.api import app

    with TestClient(app) as c:
        r = c.post("/api/chat", json={"question": "1+1=?"})
    assert r.status_code == 503
    cfg.settings.require_auth = False
    cfg.settings.jwt_secret = None
    reset_limiter()


def test_health_minimal_when_public_detail_off(client, monkeypatch):
    monkeypatch.setattr(cfg.settings, "health_public_detail", False)
    monkeypatch.setattr(cfg.settings, "api_keys", None)
    h = client.get("/api/health").json()
    assert h["status"] == "ok"
    assert "llm_model" not in h
