"""学情 GapMap 服务（knowledge_point_id 主轴）。"""

from __future__ import annotations

from datetime import datetime, timezone

from . import storage
from .error_taxonomy import MASTERED_STREAK
from .kp_catalog import get_kp
from .schemas import AttemptRecord, GapEntry, GapStatus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gap_store(student_id: str) -> dict[str, dict]:
    raw = storage.get_student_singleton("gaps.json", student_id) or {}
    return raw.get("gaps", {})


def _save_gaps(student_id: str, gaps: dict[str, dict]) -> None:
    storage.upsert_student_singleton("gaps.json", student_id, {"gaps": gaps})


def list_gaps(student_id: str) -> list[GapEntry]:
    store = _gap_store(student_id)
    out: list[GapEntry] = []
    for kp_id, row in store.items():
        kp = get_kp(kp_id)
        title = kp.title if kp else row.get("title", kp_id)
        out.append(GapEntry(knowledge_point_id=kp_id, title=title, **{
            k: v for k, v in row.items() if k not in ("title",)
        }))
    out.sort(key=lambda g: (g.status != "weak", g.status != "learning", g.title))
    return out


def apply_attempt(student_id: str, attempt: AttemptRecord) -> GapEntry:
    gaps = _gap_store(student_id)
    kp_id = attempt.knowledge_point_id
    kp = get_kp(kp_id)
    title = kp.title if kp else kp_id
    row = gaps.get(kp_id, {
        "title": title,
        "status": "unknown",
        "correct_streak": 0,
        "attempt_count": 0,
        "last_attempt_id": None,
        "provenance": attempt.source,
        "updated_at": _now(),
    })

    row["attempt_count"] = row.get("attempt_count", 0) + 1
    row["last_attempt_id"] = attempt.attempt_id
    row["updated_at"] = _now()
    row["provenance"] = attempt.source

    if attempt.is_correct:
        row["correct_streak"] = row.get("correct_streak", 0) + 1
        if row["correct_streak"] >= MASTERED_STREAK:
            row["status"] = "mastered"
        elif row.get("status") == "weak":
            row["status"] = "learning"
        elif row.get("status") == "unknown":
            row["status"] = "learning"
    else:
        row["correct_streak"] = 0
        row["status"] = "weak"

    gaps[kp_id] = row
    _save_gaps(student_id, gaps)
    return GapEntry(knowledge_point_id=kp_id, **row)


def override_gap(student_id: str, kp_id: str, status: GapStatus, note: str = "") -> GapEntry:
    gaps = _gap_store(student_id)
    kp = get_kp(kp_id)
    title = kp.title if kp else kp_id
    row = gaps.get(kp_id, {"title": title, "correct_streak": 0, "attempt_count": 0})
    row["status"] = status
    row["provenance"] = "manual_override"
    row["updated_at"] = _now()
    if note:
        row["override_note"] = note
    gaps[kp_id] = row
    _save_gaps(student_id, gaps)
    return GapEntry(knowledge_point_id=kp_id, **row)


def weak_kp_ids(student_id: str) -> list[str]:
    return [g.knowledge_point_id for g in list_gaps(student_id) if g.status == "weak"]
