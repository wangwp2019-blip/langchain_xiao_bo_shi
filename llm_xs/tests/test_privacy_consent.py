"""家长同意、数据留存与 API async 测试。"""

from __future__ import annotations

import pytest

import app.config as cfg
from app.privacy import clear_consents_for_tests, delete_all_user_data, get_policy, record_consent, sweep_expired_audit_data
from app.security import derive_user_id

_OPEN_PRINCIPAL = "ip:testclient"


@pytest.fixture(autouse=True)
def _reset_consent_file():
    clear_consents_for_tests()
    yield
    clear_consents_for_tests()


def test_privacy_policy_public(client):
    r = client.get("/api/privacy/policy")
    assert r.status_code == 200
    body = r.json()
    assert "version" in body
    assert "parent_rights" in body


def test_consent_record_and_status(client, monkeypatch):
    monkeypatch.setattr(cfg.settings, "require_parent_consent", True)
    sub = "consent-test-user"

    status0 = client.get(f"/api/privacy/consent?sub={sub}").json()
    assert status0["valid"] is False

    r = client.post(
        "/api/privacy/consent",
        json={"sub": sub, "parent_name": "张家长", "parent_email": "p@example.com"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    status = client.get(f"/api/privacy/consent?sub={sub}").json()
    assert status["valid"] is True


def test_chat_blocked_without_consent(client, monkeypatch):
    monkeypatch.setattr(cfg.settings, "require_parent_consent", True)
    uid = "no-consent-kid"
    r = client.post(
        "/api/chat",
        json={"question": "1+1=?", "user_id": uid, "thread_id": "t1"},
    )
    assert r.status_code == 200
    assert "家长" in r.json()["answer"]


def test_chat_after_consent(client, monkeypatch):
    monkeypatch.setattr(cfg.settings, "require_parent_consent", True)
    sub = "consented-kid"
    client.post("/api/privacy/consent", json={"sub": sub, "parent_name": "李家长"})
    r = client.post(
        "/api/chat",
        json={"question": "2+3=?", "user_id": sub, "thread_id": "t1"},
    )
    assert r.status_code == 200
    assert "家长" not in r.json()["answer"]


def test_delete_account(client, monkeypatch):
    monkeypatch.setattr(cfg.settings, "require_parent_consent", True)
    sub = "delete-me-user"
    client.post("/api/privacy/consent", json={"sub": sub, "parent_name": "王家长"})
    r = client.delete(f"/api/privacy/account?sub={sub}")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert client.get(f"/api/privacy/consent?sub={sub}").json()["valid"] is False


def test_retention_sweep_dev_open(client, monkeypatch):
    monkeypatch.setattr(cfg.settings, "retention_sweep_token", None)
    monkeypatch.setattr(cfg.settings, "app_env", "development")
    r = client.post("/api/privacy/retention/sweep")
    assert r.status_code == 200
    body = r.json()
    assert "skipped" in body or "chat_logs_deleted" in body


def test_get_policy_fields():
    p = get_policy()
    assert p["require_consent"] is False or isinstance(p["require_consent"], bool)
    assert p["data_retention_days"] >= 0


def test_sweep_without_mysql():
    result = sweep_expired_audit_data()
    assert "skipped" in result or "chat_logs_deleted" in result


def test_delete_all_user_data():
    sub = "purge-user-xyz"
    uid = derive_user_id(_OPEN_PRINCIPAL, sub)
    record_consent(uid, parent_name="测试家长")
    result = delete_all_user_data(uid)
    assert result["user_id"] == uid
