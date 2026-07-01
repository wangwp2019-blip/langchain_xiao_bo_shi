"""推题队列（Phase 4 PushEngine 简化版）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from . import storage
from .gap_service import weak_kp_ids
from .question_bank import question_public, suggest_questions
from .schemas import QuestionPublic


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _queue(student_id: str) -> list[dict]:
    raw = storage.get_student_singleton("push_queue.json", student_id) or {}
    return list(raw.get("items", []))


def _save(student_id: str, items: list[dict]) -> None:
    storage.upsert_student_singleton("push_queue.json", student_id, {"items": items})


def rebuild_queue(student_id: str, *, grade: int = 2, count: int = 5) -> list[dict]:
    """按薄弱 KP 重建离线推题队列。"""
    kp_ids = weak_kp_ids(student_id) or None
    qs = suggest_questions(kp_ids=kp_ids, grade=grade, count=count)
    items = [
        {
            "queue_id": f"pq-{uuid.uuid4().hex[:8]}",
            "question_id": q.question_id,
            "knowledge_point_id": q.knowledge_point_id,
            "status": "pending",
            "created_at": _now(),
        }
        for q in qs
    ]
    _save(student_id, items)
    return items


def peek(student_id: str, n: int = 3) -> list[QuestionPublic]:
    items = [i for i in _queue(student_id) if i.get("status") == "pending"][:n]
    out: list[QuestionPublic] = []
    for it in items:
        q = question_public(it["question_id"])
        if q:
            out.append(q)
    return out


def pop_next(student_id: str) -> QuestionPublic | None:
    items = _queue(student_id)
    for it in items:
        if it.get("status") == "pending":
            it["status"] = "offered"
            it["offered_at"] = _now()
            _save(student_id, items)
            return question_public(it["question_id"])
    return None


def mark_done(student_id: str, question_id: str) -> None:
    items = _queue(student_id)
    for it in items:
        if it.get("question_id") == question_id:
            it["status"] = "done"
    _save(student_id, items)
