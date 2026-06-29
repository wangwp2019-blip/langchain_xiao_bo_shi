"""MySQL 预留层单元测试（不依赖真实 MySQL 服务）。"""

from __future__ import annotations

import pytest

import app.config as cfg
from app.mysql_db import (
    check_mysql_ready,
    close_mysql_pool,
    mysql_connection_params,
    parse_mysql_url,
)


def test_parse_mysql_url():
    params = parse_mysql_url("mysql://kid:secret@db.example.com:3307/kid_assistant?charset=utf8mb4")
    assert params["host"] == "db.example.com"
    assert params["port"] == 3307
    assert params["user"] == "kid"
    assert params["password"] == "secret"
    assert params["database"] == "kid_assistant"
    assert params["charset"] == "utf8mb4"


def test_parse_mysql_pymysql_prefix():
    params = parse_mysql_url("mysql+pymysql://u:p@127.0.0.1/kids")
    assert params["user"] == "u"
    assert params["database"] == "kids"


def test_mysql_not_configured_by_default(monkeypatch):
    monkeypatch.setattr(cfg.settings, "mysql_url", None)
    monkeypatch.setattr(cfg.settings, "mysql_user", None)
    assert mysql_connection_params() is None
    assert cfg.settings.mysql_configured is False
    ready = check_mysql_ready()
    assert ready["configured"] is False
    assert ready["ready"] is False


def test_mysql_params_from_parts(monkeypatch):
    monkeypatch.setattr(cfg.settings, "mysql_url", None)
    monkeypatch.setattr(cfg.settings, "mysql_user", "kid")
    monkeypatch.setattr(cfg.settings, "mysql_password", "kid")
    monkeypatch.setattr(cfg.settings, "mysql_database", "kid_assistant")
    params = mysql_connection_params()
    assert params is not None
    assert params["user"] == "kid"
    assert params["database"] == "kid_assistant"


def test_close_mysql_pool_idempotent():
    close_mysql_pool()
    close_mysql_pool()


def test_repository_import():
    from app.mysql import ChatLogRepository, QuizRecordRepository, UserProfileRepository

    assert UserProfileRepository().TABLE == "kids_user_profiles"
    assert ChatLogRepository().TABLE == "kids_chat_logs"
    assert QuizRecordRepository().TABLE == "kids_quiz_records"
