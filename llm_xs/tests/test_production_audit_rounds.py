"""生产门禁与上线审计回归测试（第七～九轮）。"""

from __future__ import annotations

import pytest

import app.config as cfg


def test_health_minimal_when_detail_off(client, monkeypatch):
    monkeypatch.setattr(cfg.settings, "health_public_detail", False)
    monkeypatch.setattr(cfg.settings, "llm_model", "secret-model")
    h = client.get("/api/health").json()
    assert h == {"status": "ok", "env": cfg.settings.app_env}
    assert "llm_model" not in h


def test_embedded_ui_disabled_in_production(client, monkeypatch):
    monkeypatch.setattr(cfg.settings, "app_env", "production")
    monkeypatch.setattr(cfg.settings, "embedded_ui_enabled", False)
    r = client.get("/")
    assert r.status_code == 404


def test_embedded_ui_enabled_override(client, monkeypatch):
    monkeypatch.setattr(cfg.settings, "app_env", "production")
    monkeypatch.setattr(cfg.settings, "embedded_ui_enabled", True)
    r = client.get("/")
    assert r.status_code == 200
    assert "小博士" in r.text


def test_validate_production_cors_wildcard(monkeypatch):
    monkeypatch.setattr(cfg.settings, "app_env", "production")
    monkeypatch.setattr(cfg.settings, "require_auth", False)
    monkeypatch.setattr(cfg.settings, "cors_origins", "*")
    monkeypatch.setattr(cfg.settings, "api_keys", "test-key")
    monkeypatch.setattr(cfg.settings, "jwt_secret", None)
    monkeypatch.setattr(cfg.settings, "ingest_token", "ingest")
    monkeypatch.setattr(cfg.settings, "require_parent_consent", True)
    monkeypatch.setattr(cfg.settings, "retention_sweep_token", "sweep")
    monkeypatch.setattr(cfg.settings, "trusted_proxy_hops", 1)
    monkeypatch.setattr(cfg.settings, "ratelimit_fail_open", False)
    monkeypatch.setattr(cfg.settings, "memory_backend", "postgres")
    monkeypatch.setattr(cfg.settings, "redis_url", "redis://localhost:6379/0")
    errs = cfg.settings.validate_production()
    assert any("CORS" in e for e in errs)


def test_validate_production_requires_credentials(monkeypatch):
    monkeypatch.setattr(cfg.settings, "app_env", "production")
    monkeypatch.setattr(cfg.settings, "api_keys", None)
    monkeypatch.setattr(cfg.settings, "jwt_secret", None)
    errs = cfg.settings.validate_production()
    assert any("KIDS_API_KEYS" in e or "KIDS_JWT_SECRET" in e for e in errs)


def test_validate_production_jwt_only_ok(monkeypatch):
    monkeypatch.setattr(cfg.settings, "app_env", "production")
    monkeypatch.setattr(cfg.settings, "api_keys", None)
    monkeypatch.setattr(cfg.settings, "jwt_secret", "jwt-secret")
    monkeypatch.setattr(cfg.settings, "cors_origins", "https://app.example.com")
    monkeypatch.setattr(cfg.settings, "ingest_token", "ingest")
    monkeypatch.setattr(cfg.settings, "require_parent_consent", True)
    monkeypatch.setattr(cfg.settings, "retention_sweep_token", "sweep")
    monkeypatch.setattr(cfg.settings, "trusted_proxy_hops", 1)
    monkeypatch.setattr(cfg.settings, "ratelimit_fail_open", False)
    monkeypatch.setattr(cfg.settings, "memory_backend", "postgres")
    monkeypatch.setattr(cfg.settings, "redis_url", "redis://localhost:6379/0")
    errs = cfg.settings.validate_production()
    assert not any("开放模式" in e for e in errs)


def test_retention_sweep_forbidden_in_production(client, monkeypatch):
    monkeypatch.setattr(cfg.settings, "app_env", "production")
    monkeypatch.setattr(cfg.settings, "retention_sweep_token", None)
    r = client.post("/api/privacy/retention/sweep")
    assert r.status_code == 403


def test_retention_sweep_with_token(client, monkeypatch):
    monkeypatch.setattr(cfg.settings, "app_env", "production")
    monkeypatch.setattr(cfg.settings, "retention_sweep_token", "cron-secret")
    r = client.post(
        "/api/privacy/retention/sweep",
        headers={"X-Retention-Token": "cron-secret"},
    )
    assert r.status_code == 200


def test_moderation_fail_closed(monkeypatch):
    from app.safety import SafetyAction, _check_openai_moderation

    monkeypatch.setattr(cfg.settings, "moderation_enabled", True)
    monkeypatch.setattr(cfg.settings, "moderation_api_key", "sk-test")
    monkeypatch.setattr(cfg.settings, "moderation_fail_open", False)

    def _boom(*args, **kwargs):
        raise ConnectionError("moderation down")

    monkeypatch.setattr("httpx.post", _boom)
    verdict = _check_openai_moderation("hello")
    assert verdict is not None
    assert verdict.action == SafetyAction.BLOCK


def test_metrics_includes_audit_failures_and_worker(client, metrics_headers):
    r = client.get("/api/metrics", headers=metrics_headers)
    body = r.text
    assert "kid_audit_write_failures_total" in body
    assert "kid_gunicorn_workers" in body or "kid_uptime_seconds" in body


def test_metrics_prometheus_content_type(client, metrics_headers):
    r = client.get("/api/metrics", headers=metrics_headers)
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "")
    assert "kid_requests_total" in r.text
    assert "# TYPE kid_requests_total counter" in r.text
