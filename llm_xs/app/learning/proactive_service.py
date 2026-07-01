"""练后小结 / 主动提醒（C-PROACT 简化版）。"""

from __future__ import annotations

from datetime import datetime, timezone

from . import attempt_service, gap_service, storage
from .schemas import AttemptRecord


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def after_attempt_message(student_id: str, attempt: AttemptRecord) -> str | None:
    """attempt 提交后生成练后小结（不刷屏）。"""
    if attempt.is_correct:
        gaps = gap_service.list_gaps(student_id)
        mastered = [g for g in gaps if g.status == "mastered"]
        if mastered:
            return f"太棒了！「{mastered[-1].title}」已经掌握啦 🌟 要不要休息一下？"
        return "答对了！继续保持～"
    return f"这题还可以再想想。{attempt.feedback} 需要我讲讲相关知识点吗？"


def list_proactive_messages(student_id: str, limit: int = 5) -> list[dict]:
    return storage.load_student_bucket("proactive.json", student_id)[-limit:]


def record_proactive(student_id: str, message: str, kind: str = "tip") -> None:
    storage.append_student_record(
        "proactive.json",
        student_id,
        {"message": message, "kind": kind, "created_at": _now()},
    )


def check_recurrence_reminder(student_id: str) -> str | None:
    """薄弱点复发提醒。"""
    weak = gap_service.weak_kp_ids(student_id)
    if not weak:
        return None
    recent = attempt_service.list_attempts(student_id, limit=3)
    if len(recent) >= 2 and not recent[0].is_correct:
        from .kp_catalog import get_kp

        kp = get_kp(weak[0])
        title = kp.title if kp else weak[0]
        msg = f"上次「{title}」还需要巩固，要不要一起练两题？"
        record_proactive(student_id, msg, "recurrence")
        return msg
    return None
