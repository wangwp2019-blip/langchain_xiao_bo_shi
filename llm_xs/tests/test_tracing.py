"""LangSmith / OpenTelemetry 追踪初始化测试。"""

from __future__ import annotations

import app.config as cfg
from app.tracing import init_tracing, shutdown_tracing


def test_tracing_disabled_by_default(monkeypatch):
    monkeypatch.setattr(cfg.settings, "enable_tracing", False)
    monkeypatch.setattr(cfg.settings, "otel_enabled", False)
    status = init_tracing()
    assert status["langsmith"] is False
    assert status["opentelemetry"] is False
    shutdown_tracing()


def test_langsmith_flag(monkeypatch):
    monkeypatch.setattr(cfg.settings, "enable_tracing", True)
    monkeypatch.setattr(cfg.settings, "otel_enabled", False)
    status = init_tracing()
    assert status["langsmith"] is True
    shutdown_tracing()


def test_health_includes_tracing(client):
    h = client.get("/api/health").json()
    assert "tracing" in h
    assert "langsmith" in h["tracing"]
