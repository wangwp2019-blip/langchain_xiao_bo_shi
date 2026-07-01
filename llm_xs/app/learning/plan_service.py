"""20 分钟微计划 + 家长周报。"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone

from . import attempt_service, gap_service, photo_service, storage
from .dimension_service import behavior_tags, compute_dimension_scores
from .kp_catalog import get_kp
from .question_bank import suggest_questions
from .schemas import ParentReport, StudyPlan, StudyPlanStep


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_plan(student_id: str, minutes: int = 20) -> StudyPlan:
    profile = attempt_service.get_profile(student_id)
    grade = profile.grade_level if profile else 2
    weak_ids = gap_service.weak_kp_ids(student_id)
    steps: list[StudyPlanStep] = []
    step_n = 1

    if weak_ids:
        kp = get_kp(weak_ids[0])
        title = kp.title if kp else weak_ids[0]
        steps.append(StudyPlanStep(step=step_n, title=f"复习：{title}", action="explain_kp", knowledge_point_id=weak_ids[0], duration_min=5))
        step_n += 1

    qs = suggest_questions(kp_ids=weak_ids or None, grade=grade, count=2)
    for q in qs:
        steps.append(StudyPlanStep(step=step_n, title=f"练习：{q.prompt[:20]}…", action="question", knowledge_point_id=q.knowledge_point_id, duration_min=5))
        step_n += 1

    if len(steps) < 3:
        steps.append(StudyPlanStep(step=step_n, title="自由聊天答疑", action="chat", duration_min=5))
        step_n += 1

    steps.append(StudyPlanStep(step=step_n, title="练后小结", action="reflect", duration_min=3))

    plan = StudyPlan(
        plan_id=f"plan-{uuid.uuid4().hex[:10]}",
        student_id=student_id,
        title="今日 20 分钟微计划",
        steps=steps,
        total_minutes=minutes,
        created_at=_now(),
    )
    storage.append_student_record("plans.json", student_id, plan.model_dump())
    return plan


def generate_parent_report(student_id: str, days: int = 7) -> ParentReport:
    gaps = gap_service.list_gaps(student_id)
    attempts = attempt_service.list_attempts(student_id, limit=100)
    inbox = photo_service.list_inbox(student_id=student_id)

    knowledge_section = [
        {"kp_id": g.knowledge_point_id, "title": g.title, "status": g.status, "attempts": g.attempt_count}
        for g in gaps
    ]

    dim_scores = compute_dimension_scores(student_id, days)
    err_counts: Counter[str] = Counter(a.error_code for a in attempts if a.error_code)

    correct = sum(1 for a in attempts if a.is_correct)
    total = len(attempts) or 1
    weak_count = sum(1 for g in gaps if g.status == "weak")
    mastered_count = sum(1 for g in gaps if g.status == "mastered")
    correct_rate = round(correct / total, 2) if attempts else None

    summary = (
        f"近 {days} 天共练习 {len(attempts)} 次，正确率 {round(correct/total*100)}%。"
        f"掌握 {mastered_count} 个知识点，需巩固 {weak_count} 个。"
    )
    habits = behavior_tags(student_id, days)
    if inbox:
        habits.append(f"有 {len(inbox)} 条拍照待家长确认归类。")

    suggestions = []
    if weak_count:
        suggestions.append("优先复习标记为「需巩固」的知识点，配合讲解后再练 2 题。")
    if dim_scores.get("审题能力", 0) > 0.3:
        suggestions.append("应用题审题可多用「画线段图」方法。")
    if not suggestions:
        suggestions.append("继续保持，可尝试拓展下一单元。")

    evidence = [
        {"type": "attempt", "id": a.attempt_id, "prompt": a.prompt[:60], "correct": a.is_correct}
        for a in attempts[:10]
    ]

    report = ParentReport(
        student_id=student_id,
        period_days=days,
        summary=summary,
        attempts_total=len(attempts),
        correct_rate=correct_rate,
        mastered_count=mastered_count,
        weak_count=weak_count,
        knowledge_section=knowledge_section,
        dimension_scores=dim_scores,
        habit_notes=habits,
        suggestions=suggestions,
        evidence=evidence,
        generated_at=_now(),
    )
    storage.append_student_record("reports.json", student_id, report.model_dump())
    return report
