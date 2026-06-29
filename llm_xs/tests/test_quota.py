"""每用户每日配额测试（进程内计数，无需 Redis）。"""

from __future__ import annotations

import pytest

import app.config as cfg
from app.quota import QuotaExceeded, check_and_consume, reset_quota_for_tests


@pytest.fixture(autouse=True)
def _reset():
    reset_quota_for_tests()
    original = cfg.settings.llm_daily_quota_per_user
    yield
    cfg.settings.llm_daily_quota_per_user = original
    reset_quota_for_tests()


def test_quota_disabled_allows_unlimited():
    cfg.settings.llm_daily_quota_per_user = 0
    for _ in range(100):
        check_and_consume("ip:1.2.3.4")  # 不抛异常即通过


def test_quota_enforced_per_principal():
    cfg.settings.llm_daily_quota_per_user = 3
    p = "jwt:user-a"
    for _ in range(3):
        check_and_consume(p)
    with pytest.raises(QuotaExceeded) as exc:
        check_and_consume(p)
    assert exc.value.limit == 3
    assert exc.value.retry_after > 0


def test_quota_isolated_between_users():
    cfg.settings.llm_daily_quota_per_user = 2
    check_and_consume("jwt:user-a")
    check_and_consume("jwt:user-a")
    # user-b 不受 user-a 影响
    check_and_consume("jwt:user-b")
    check_and_consume("jwt:user-b")
    with pytest.raises(QuotaExceeded):
        check_and_consume("jwt:user-b")


def test_quota_chat_endpoint_returns_429(client, monkeypatch):
    """在线 + 配额=1 时，第二次 /api/chat 返回 429。"""
    monkeypatch.setattr(cfg.settings, "llm_daily_quota_per_user", 1)
    # 强制 llm_configured=True，避免真实调用：mock guardrail
    monkeypatch.setattr(cfg.settings, "llm_api_key", "test-key")
    monkeypatch.setattr(cfg.settings, "llm_base_url", "http://test")

    import app.api as api

    async def _fake_answer(*args, **kwargs):
        return "你好呀小朋友～"

    monkeypatch.setattr(api, "_answer_with_guardrails_async", _fake_answer)

    r1 = client.post("/api/chat", json={"question": "你好", "user_id": "kid", "thread_id": "t"})
    assert r1.status_code == 200
    r2 = client.post("/api/chat", json={"question": "再问", "user_id": "kid", "thread_id": "t"})
    assert r2.status_code == 429
    assert "Retry-After" in r2.headers
