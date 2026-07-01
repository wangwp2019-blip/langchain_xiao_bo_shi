"""StudentContext 聚合 + T4 鼓励性进度视图。"""

from __future__ import annotations

from . import attempt_service, gap_service, photo_service
from .schemas import GapEntry, ProgressView, StudentContext


def build_context(student_id: str) -> StudentContext:
    profile = attempt_service.get_profile(student_id)
    gaps = gap_service.list_gaps(student_id)
    weak = [g for g in gaps if g.status == "weak"][:5]
    attempts = attempt_service.list_attempts(student_id, limit=5)
    pending = len(photo_service.list_inbox(student_id=student_id))
    mastered = sum(1 for g in gaps if g.status == "mastered")
    return StudentContext(
        student_id=student_id,
        profile=profile,
        top_gaps=weak,
        mastered_count=mastered,
        total_kp_tracked=len(gaps),
        recent_attempts=attempts,
        pending_photos=pending,
    )


def build_progress_view(student_id: str) -> ProgressView:
    gaps = gap_service.list_gaps(student_id)
    attempts = attempt_service.list_attempts(student_id, limit=50)
    mastered = [g.title for g in gaps if g.status == "mastered"][:5]
    learning = [g.title for g in gaps if g.status in ("learning", "weak")][:3]
    wins = [a.feedback for a in attempts if a.is_correct][:3]
    total = len(attempts)
    enc = "你已经很棒啦！"
    if mastered:
        enc = f"你已经掌握了 {len(mastered)} 个知识点，继续加油！🌟"
    elif total > 0:
        enc = f"你已经练习了 {total} 次，每一步都在进步！💪"
    else:
        enc = "欢迎和小博士一起学习，一起探索新知识吧！🎈"
    return ProgressView(
        student_id=student_id,
        encouragement=enc,
        mastered_titles=mastered,
        learning_titles=learning,
        streak_days=min(total // 3, 7),
        total_attempts=total,
        recent_wins=wins or ["准备好开始第一次练习了吗？"],
    )


def format_context_for_prompt(student_id: str) -> str:
    ctx = build_context(student_id)
    lines = ["【当前学情摘要】"]
    if ctx.profile:
        lines.append(f"- 年级：{ctx.profile.grade} · 学科：{ctx.profile.subject}")
    if ctx.top_gaps:
        lines.append("- 需关注知识点（有练习证据）：")
        for g in ctx.top_gaps[:3]:
            lines.append(f"  · {g.title}（gap_id={g.knowledge_point_id}, status={g.status}）")
    else:
        lines.append("- 暂无薄弱知识点记录（不要臆造薄弱项）")
    if ctx.recent_attempts:
        a = ctx.recent_attempts[0]
        lines.append(f"- 最近一次练习 attempt_id={a.attempt_id}，{'正确' if a.is_correct else '需巩固'}")
    lines.append(
        "【AnswerGate】谈及薄弱/掌握时必须引用 gap_id 或 attempt_id；"
        "无证据领域须说明「还没有这方面练习记录」。"
    )
    return "\n".join(lines)
