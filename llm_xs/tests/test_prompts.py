"""Prompt 模板与个性化注入测试。"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

import app.config as cfg
from app.graph.nodes import _ensure_system_message
from app.graph.prompts import (
    DEFAULT_KIDS_SYSTEM_PROMPT,
    KIDS_SYSTEM_PROMPT,
    PromptContext,
    build_kids_system_prompt,
    build_study_card_user_prompt,
    clear_prompt_cache,
    get_suggested_prompts,
    load_prompt_context,
)
from app.memory_admin import clear_memories, remember_fact, save_profile


def test_default_system_prompt_backward_compat():
    assert KIDS_SYSTEM_PROMPT == DEFAULT_KIDS_SYSTEM_PROMPT
    assert build_kids_system_prompt() == DEFAULT_KIDS_SYSTEM_PROMPT


def test_build_system_prompt_with_profile():
    ctx = PromptContext(name="小明", grade="三年级", facts=["喜欢恐龙"])
    text = build_kids_system_prompt(ctx)
    assert "小明" in text
    assert "三年级" in text
    assert "喜欢恐龙" in text


def test_build_system_prompt_extra(monkeypatch):
    monkeypatch.setenv("KIDS_SYSTEM_PROMPT_EXTRA", "回答时尽量用 emoji。")
    cfg.settings.system_prompt_extra = "回答时尽量用 emoji。"
    clear_prompt_cache()
    try:
        assert "emoji" in build_kids_system_prompt()
    finally:
        cfg.settings.system_prompt_extra = None
        clear_prompt_cache()


def test_load_prompt_context_from_memory():
    uid = "prompt-test-user"
    clear_memories(uid)
    save_profile(uid, "小红", "二年级")
    remember_fact(uid, "数学乘法还不太熟")
    ctx = load_prompt_context(uid)
    assert ctx.name == "小红"
    assert ctx.grade == "二年级"
    assert any("乘法" in f for f in ctx.facts)
    clear_memories(uid)


def test_ensure_system_message_injects_profile(client):
    uid = "graph-prompt-user"
    clear_memories(uid)
    save_profile(uid, "小华", "四年级")
    msgs = _ensure_system_message([HumanMessage("你好")], uid)
    assert isinstance(msgs[0], SystemMessage)
    assert "小华" in msgs[0].content
    assert "四年级" in msgs[0].content
    clear_memories(uid)


def test_study_card_user_prompt():
    text = build_study_card_user_prompt("什么是光合作用？", "资料A", grade="五年级")
    assert "光合作用" in text
    assert "五年级" in text
    assert "资料A" in text


def test_suggested_prompts_by_grade():
    all_zh = get_suggested_prompts(lang="zh", limit=20)
    assert len(all_zh) >= 8
    g3 = get_suggested_prompts(grade="三年级", lang="zh", limit=20)
    assert any("3 × 7" in p["text"] for p in g3)
    en = get_suggested_prompts(lang="en", limit=3)
    assert en[0]["text"].startswith("How") or "What" in en[0]["text"]


def test_prompt_suggestions_api(client):
    r = client.get("/api/prompts/suggestions?lang=zh&limit=5")
    assert r.status_code == 200
    data = r.json()
    assert len(data["prompts"]) == 5
    assert "text" in data["prompts"][0]
    assert "category" in data["prompts"][0]
