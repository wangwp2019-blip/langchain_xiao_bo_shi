"""Attempt 提交：题库题 + freeform 真实题。"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from ..config import settings
from . import gap_service, storage
from .error_taxonomy import infer_error_code, kp_for_error
from .kp_catalog import assert_student_may_access_unit, get_kp, resolve_grade_level
from .question_bank import grade_answer
from .schemas import AttemptRecord, FreeformAttemptRequest, OnboardingProfile


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "att") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def get_profile(student_id: str) -> OnboardingProfile | None:
    raw = storage.get_student_singleton("profiles.json", student_id)
    return OnboardingProfile.model_validate(raw) if raw else None


def save_profile(profile: OnboardingProfile) -> OnboardingProfile:
    storage.upsert_student_singleton("profiles.json", profile.student_id, profile.model_dump())
    return profile


def list_attempts(student_id: str, limit: int = 20) -> list[AttemptRecord]:
    rows = storage.load_student_bucket("attempts.json", student_id)
    items = [AttemptRecord.model_validate(r) for r in rows[-limit:]]
    return list(reversed(items))


def submit_bank_attempt(student_id: str, question_id: str, answer: str) -> AttemptRecord:
    ok, explanation, qmeta = grade_answer(question_id, answer)
    error_code = None if ok else infer_error_code(qmeta["prompt"], answer, qmeta["answer"])
    kp_id = qmeta["knowledge_point_id"] if ok else kp_for_error(error_code)

    profile = get_profile(student_id)
    if profile:
        assert_student_may_access_unit(profile.grade_level, qmeta["unit_id"])

    attempt = AttemptRecord(
        attempt_id=_new_id(),
        student_id=student_id,
        question_id=question_id,
        knowledge_point_id=kp_id,
        is_correct=ok,
        error_code=error_code,
        source="bank",
        prompt=qmeta["prompt"],
        student_answer=answer,
        feedback="太棒了！答对了 🎉" if ok else f"再想想～ {explanation}",
        created_at=_now(),
    )
    storage.append_student_record("attempts.json", student_id, attempt.model_dump())
    gap_service.apply_attempt(student_id, attempt)
    _after_attempt(student_id, attempt)
    return attempt


def _after_attempt(student_id: str, attempt: AttemptRecord) -> None:
    from . import evolution_service, proactive_service

    msg = proactive_service.after_attempt_message(student_id, attempt)
    if msg:
        proactive_service.record_proactive(student_id, msg, "after_attempt")
    if attempt.is_correct and attempt.knowledge_point_id:
        hint = evolution_service.get_remediation_hint(student_id, attempt.knowledge_point_id)
        if hint:
            evolution_service.promote_skill(
                student_id, attempt.knowledge_point_id, hint, attempt.attempt_id
            )


def submit_freeform(student_id: str, req: FreeformAttemptRequest) -> AttemptRecord:
    ok, feedback, kp_id, error_code = _grade_freeform(req)
    attempt = AttemptRecord(
        attempt_id=_new_id(),
        student_id=student_id,
        knowledge_point_id=kp_id,
        is_correct=ok,
        error_code=error_code,
        source="freeform",
        prompt=req.prompt,
        student_answer=req.student_answer,
        feedback=feedback,
        created_at=_now(),
    )
    storage.append_student_record("attempts.json", student_id, attempt.model_dump())
    gap_service.apply_attempt(student_id, attempt)
    _after_attempt(student_id, attempt)
    return attempt


def _grade_freeform(req: FreeformAttemptRequest) -> tuple[bool, str, str, str | None]:
    """LLM 判分（在线）或规则兜底（离线）。"""
    if settings.llm_configured:
        try:
            return _grade_freeform_llm(req)
        except Exception:
            pass
    return _grade_freeform_offline(req)


def _extract_number(s: str) -> str | None:
    m = re.search(r"-?\d+(?:\.\d+)?", s.replace(" ", ""))
    return m.group(0) if m else None


def _grade_freeform_offline(req: FreeformAttemptRequest) -> tuple[bool, str, str, str | None]:
    prompt = req.prompt
    ans = req.student_answer.strip()
    # 简单算式提取
    expr_m = re.search(r"(\d+)\s*([+\-×x*])\s*(\d+)", prompt.replace("=", ""))
    if expr_m:
        a, op, b = int(expr_m.group(1)), expr_m.group(2), int(expr_m.group(3))
        expected = a + b if op in "+＋" else a - b if op in "-－" else a * b
        given = _extract_number(ans)
        ok = given is not None and int(float(given)) == expected
        err = None if ok else infer_error_code(prompt, ans, str(expected))
        kp = kp_for_error(err) if not ok else "kp-g2-add-no-carry"
        fb = "答对了！继续加油 🌟" if ok else "这题还可以再想想，注意计算步骤哦。"
        return ok, fb, kp, err
    ok = len(ans) >= 2
    return ok, "已记录你的作答，我们一起继续学！", "kp-g2-add-no-carry", None


def _grade_freeform_llm(req: FreeformAttemptRequest) -> tuple[bool, str, str, str | None]:
    from langchain.chat_models import init_chat_model

    model = init_chat_model(
        settings.llm_model,
        model_provider=settings.llm_provider,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )
    prompt = (
        "你是小学数学判题助手。给定题目和学生答案，输出 JSON："
        '{"is_correct": true/false, "feedback": "...", "error_code": "CARRY_ERROR|BORROW_ERROR|...|null"}'
        f"\n题目：{req.prompt}\n学生答案：{req.student_answer}"
    )
    resp = model.invoke(prompt)
    text = resp.content if hasattr(resp, "content") else str(resp)
    import json

    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return _grade_freeform_offline(req)
    data = json.loads(m.group())
    ok = bool(data.get("is_correct"))
    err = data.get("error_code")
    kp = kp_for_error(err) if not ok else "kp-g2-add-no-carry"
    return ok, str(data.get("feedback", "")), kp, err


def onboard(student_id: str, grade: str, subject: str, unit_id: str | None, self_assessment: str | None) -> OnboardingProfile:
    level = resolve_grade_level(grade)
    if unit_id:
        assert_student_may_access_unit(level, unit_id)
    profile = OnboardingProfile(
        student_id=student_id,
        grade=grade,
        grade_level=level,
        subject=subject,
        unit_id=unit_id,
        self_assessment=self_assessment,
        onboarded_at=_now(),
    )
    return save_profile(profile)
