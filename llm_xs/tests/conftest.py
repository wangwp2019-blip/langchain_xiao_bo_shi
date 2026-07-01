"""pytest 公共 fixture：TestClient + 环境隔离。"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

import app.config as cfg
import app.ratelimit as rl
from app.ratelimit import reset_limiter

# TestClient 的 client.host 为 "testclient"，无法走 /metrics 本机白名单。
TEST_METRICS_TOKEN = "pytest-metrics-token"


def _reset_limiter() -> None:
    reset_limiter()


def _open_settings() -> None:
    """开放模式：无鉴权、宽松限流、metrics 用 Token 绕过 host 限制。"""
    cfg.settings.api_keys = None
    cfg.settings.api_rate_limit_per_min = 1000
    cfg.settings.metrics_token = TEST_METRICS_TOKEN
    cfg.settings.max_body_bytes = 64 * 1024
    cfg.settings.vector_backend = "keyword"
    cfg.settings.moderation_enabled = False
    cfg.settings.health_public_detail = True
    cfg.settings.app_env = "development"
    cfg.settings.require_auth = False
    cfg.settings.jwt_secret = None
    cfg.settings.require_parent_consent = False
    cfg.settings.simple_chat_mode = False
    cfg.settings.knowledge_scope_filter = False
    _reset_limiter()
    from app.graph.prompts import clear_prompt_cache

    clear_prompt_cache()


@pytest.fixture(autouse=True)
def _apply_test_settings():
    _open_settings()
    yield


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """开放模式 TestClient（无鉴权、宽松限流）。"""
    monkeypatch.setenv("KIDS_API_KEYS", "")
    monkeypatch.setenv("KIDS_API_RATE_LIMIT_PER_MIN", "1000")
    _open_settings()

    from app.api import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """开启鉴权的 TestClient。"""
    monkeypatch.setenv("KIDS_API_KEYS", "test-secret-key")
    cfg.settings.api_keys = "test-secret-key"
    cfg.settings.api_rate_limit_per_min = 1000
    cfg.settings.metrics_token = TEST_METRICS_TOKEN
    _reset_limiter()

    from app.api import app

    with TestClient(app) as c:
        yield c

    cfg.settings.api_keys = os.getenv("KIDS_API_KEYS") or None


@pytest.fixture()
def metrics_headers() -> dict[str, str]:
    return {"X-Metrics-Token": TEST_METRICS_TOKEN}


@pytest.fixture()
def keyword_backend(monkeypatch: pytest.MonkeyPatch):
    """强制 keyword 向量后端（零 Embedding），测试后恢复。"""
    original = cfg.settings.vector_backend
    monkeypatch.setenv("KIDS_VECTOR_BACKEND", "keyword")
    cfg.settings.vector_backend = "keyword"
    from app.vector_store import get_vector_store

    get_vector_store.cache_clear()
    yield
    cfg.settings.vector_backend = original
    get_vector_store.cache_clear()
