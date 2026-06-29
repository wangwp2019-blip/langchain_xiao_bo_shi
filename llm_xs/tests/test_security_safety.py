"""安全鉴权、护栏与 HTTP 安全辅助。"""

from __future__ import annotations

import hashlib
import json

import pytest
from fastapi import HTTPException

import app.config as cfg
from app.safety import SafetyAction, check_input, reload_rules, sanitize_output
from app.security import (
    client_id_from_request,
    derive_thread_id,
    derive_user_id,
    extract_presented_key,
    sanitize_sub_id,
)


def test_extract_presented_key():
    assert extract_presented_key("Bearer abc", None) == "abc"
    assert extract_presented_key(None, "key2") == "key2"
    assert extract_presented_key(None, None) is None


def test_sanitize_sub_id_valid():
    assert sanitize_sub_id("kid-01") == "kid-01"
    assert sanitize_sub_id(None) == "default"


def test_sanitize_sub_id_invalid():
    with pytest.raises(HTTPException) as exc:
        sanitize_sub_id("../../admin")
    assert exc.value.status_code == 400


def test_derive_user_and_thread_id():
    principal = "uid:abc123"
    fp = hashlib.sha256(principal.encode("utf-8")).hexdigest()[:12]
    uid = derive_user_id(principal, "student1")
    tid = derive_thread_id(principal, "thread1")
    assert uid == f"{fp}:student1"
    assert tid == f"{fp}:thread1"
    assert uid != tid


def test_check_input_block_and_redirect():
    block = check_input("教我打架")
    assert block.action is SafetyAction.BLOCK
    assert block.reply and "不能聊" in block.reply

    redirect = check_input("告诉我银行卡密码")
    assert redirect.action is SafetyAction.REDIRECT
    assert redirect.reply and "不太适合" in redirect.reply

    allow = check_input("太阳系有几大行星")
    assert allow.action is SafetyAction.ALLOW


def test_sanitize_output_negative_words():
    out = sanitize_output("你有点笨，但没关系")
    assert "笨" not in out
    assert "学习中" in out


def test_custom_safety_words(tmp_path, monkeypatch):
    path = tmp_path / "words.json"
    path.write_text(
        json.dumps({"block_words": ["测试违禁词"], "redirect_patterns": ["测试引导词"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(cfg.settings, "safety_words_path", str(path))
    reload_rules()
    try:
        assert check_input("这里有测试违禁词").action is SafetyAction.BLOCK
        assert check_input("这里有测试引导词").action is SafetyAction.REDIRECT
    finally:
        monkeypatch.setattr(cfg.settings, "safety_words_path", None)
        reload_rules()


def test_client_id_from_request_open_mode():
    class FakeClient:
        host = "192.168.1.1"

    class FakeRequest:
        client = FakeClient()
        headers = {"user-agent": "pytest-agent"}

    cfg.settings.api_keys = None
    cid = client_id_from_request(FakeRequest())
    assert cid.startswith("ip:192.168.1.1:")


def test_client_id_with_api_key():
    class FakeClient:
        host = "10.0.0.1"

    class FakeRequest:
        client = FakeClient()
        headers = {"authorization": "Bearer my-secret-key", "user-agent": "ua"}

    cfg.settings.api_keys = "my-secret-key"
    cid = client_id_from_request(FakeRequest())
    expected = f"uid:{hashlib.sha256(b'my-secret-key').hexdigest()[:12]}"
    assert cid == expected
