"""Vision 理解会话（切片12：感知与 Agent 编排分离）。"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from ..config import settings
from . import storage
from .schemas import VisionItem, VisionUnderstandResponse


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save_session(vision_id: str, student_id: str, payload: dict) -> None:
    storage.upsert_student_singleton(
        "vision_sessions.json",
        vision_id,
        {"student_id": student_id, "created_at": _now(), **payload},
    )


def get_session(vision_id: str) -> dict | None:
    return storage.get_student_singleton("vision_sessions.json", vision_id)


def understand_text(
    student_id: str,
    text: str,
    *,
    mode: str = "homework",
) -> VisionUnderstandResponse:
    """理解 OCR/描述文本；在线 LLM 结构化，离线按行拆分。"""
    vision_id = f"vis-{uuid.uuid4().hex[:10]}"
    if settings.llm_configured:
        try:
            resp = _llm_understand(text, mode, vision_id)
            _save_session(vision_id, student_id, resp.model_dump())
            return resp
        except Exception:
            pass
    return _offline_understand(vision_id, student_id, text, mode)


def _offline_understand(
    vision_id: str, student_id: str, text: str, mode: str
) -> VisionUnderstandResponse:
    items: list[VisionItem] = []
    for i, ln in enumerate([x.strip() for x in text.splitlines() if x.strip()][:15], 1):
        is_correct = None
        if "✓" in ln or "对" in ln:
            is_correct = True
        elif "✗" in ln or "错" in ln or "×" in ln:
            is_correct = False
        items.append(VisionItem(index=i, prompt=ln, is_correct=is_correct))
    triage = "auto" if mode == "graded" and items else "inbox"
    resp = VisionUnderstandResponse(
        vision_id=vision_id,
        summary=f"识别到 {len(items)} 行内容（离线模式）",
        items=items,
        triage=triage,
    )
    _save_session(vision_id, student_id, resp.model_dump())
    return resp


def _llm_understand(text: str, mode: str, vision_id: str) -> VisionUnderstandResponse:
    from langchain.chat_models import init_chat_model

    model = init_chat_model(
        settings.llm_model,
        model_provider=settings.llm_provider,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )
    prompt = (
        "解析以下作业/批改文本，输出 JSON："
        '{"summary":"...", "image_type":"graded_homework|blank_homework", "items":[{"index":1,"prompt":"...","student_answer":"...","is_correct":true/false/null,"knowledge_point_id":null}]}'
        f"\n模式={mode}\n文本：\n{text[:3000]}"
    )
    raw = model.invoke(prompt)
    content = raw.content if hasattr(raw, "content") else str(raw)
    m = re.search(r"\{[\s\S]*\}", content)
    data = json.loads(m.group()) if m else {}
    items = [
        VisionItem(
            index=int(it.get("index", i + 1)),
            prompt=str(it.get("prompt", "")),
            student_answer=it.get("student_answer"),
            is_correct=it.get("is_correct"),
            knowledge_point_id=it.get("knowledge_point_id"),
        )
        for i, it in enumerate(data.get("items") or [])
    ]
    triage = "auto" if data.get("image_type") == "graded_homework" else "inbox"
    return VisionUnderstandResponse(
        vision_id=vision_id,
        summary=str(data.get("summary", f"识别 {len(items)} 题")),
        items=items,
        triage=triage,
    )


def format_vision_for_prompt(vision_id: str) -> str:
    sess = get_session(vision_id)
    if not sess:
        return ""
    lines = [f"【Vision 上下文 vision_id={vision_id}】", sess.get("summary", "")]
    for it in sess.get("items") or []:
        mark = it.get("is_correct")
        flag = "✓" if mark is True else "✗" if mark is False else "?"
        lines.append(f"- 第{it.get('index')}题 {flag} {it.get('prompt', '')[:80]}")
    lines.append(
        "编排规则：用户要「记错题/复盘/保存学情」时调 classify_photo；"
        "用户要「讲解/我不会」时优先讲解，不要整页 classify。"
    )
    return "\n".join(lines)
