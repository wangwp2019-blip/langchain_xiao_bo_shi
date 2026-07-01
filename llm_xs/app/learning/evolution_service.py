"""个人补救策略晋升（C-EVO 简化版）。"""

from __future__ import annotations

from datetime import datetime, timezone

from . import storage
from .kp_catalog import get_kp


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _skills(student_id: str) -> dict[str, dict]:
    return storage.get_student_singleton("remediation_skills.json", student_id) or {}


def get_remediation_hint(student_id: str, kp_id: str) -> str | None:
    skill = _skills(student_id).get(kp_id)
    if skill:
        return skill.get("strategy")
    kp = get_kp(kp_id)
    if not kp:
        return None
    defaults = {
        "kp-g2-sub-borrow": "退位减法：个位不够减，向十位借 1 当 10。",
        "kp-g2-add-carry": "进位加法：个位满十向十位进 1。",
        "kp-g2-word-problem-more-less": "比…多 → 加法；比…少 → 减法。",
    }
    return defaults.get(kp_id, f"我们一步一步练「{kp.title}」。")


def promote_skill(student_id: str, kp_id: str, strategy: str, source_attempt: str = "") -> dict:
    """连续有效补救后晋升个人技能。"""
    data = _skills(student_id)
    row = data.get(kp_id, {"success_count": 0})
    row["success_count"] = row.get("success_count", 0) + 1
    row["strategy"] = strategy
    row["updated_at"] = _now()
    row["source_attempt"] = source_attempt
    row["promoted"] = row["success_count"] >= 2
    data[kp_id] = row
    storage.upsert_student_singleton("remediation_skills.json", student_id, data)
    return row


def list_skills(student_id: str) -> list[dict]:
    data = _skills(student_id)
    out = []
    for kp_id, row in data.items():
        kp = get_kp(kp_id)
        out.append({"kp_id": kp_id, "title": kp.title if kp else kp_id, **row})
    return out
