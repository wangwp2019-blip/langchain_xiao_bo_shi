"""能力维度诊断（P0 dimension-model 简化版）。"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from . import attempt_service
from .error_taxonomy import ERROR_TO_DIMENSION

DIMENSIONS = ("基础知识", "逻辑推理", "审题能力", "细心程度", "学习习惯")


def compute_dimension_scores(student_id: str, days: int = 7) -> dict[str, float]:
    attempts = attempt_service.list_attempts(student_id, limit=200)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    counter: Counter[str] = Counter()
    total_err = 0
    for a in attempts:
        try:
            ts = datetime.fromisoformat(a.created_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts < cutoff:
            continue
        if a.error_code:
            dim = ERROR_TO_DIMENSION.get(a.error_code, "基础知识")
            counter[dim] += 1
            total_err += 1
        elif not a.is_correct:
            counter["细心程度"] += 1
            total_err += 1
    scores = {d: 0.0 for d in DIMENSIONS}
    if total_err:
        for d, c in counter.items():
            if d in scores:
                scores[d] = round(c / total_err, 2)
    return scores


def behavior_tags(student_id: str, days: int = 7) -> list[str]:
    attempts = attempt_service.list_attempts(student_id, limit=50)
    tags: list[str] = []
    if len(attempts) >= 5:
        tags.append("练习频率不错")
    wrong = sum(1 for a in attempts if not a.is_correct)
    if wrong > len(attempts) * 0.5 and attempts:
        tags.append("近期错题偏多，建议分步练")
    if not tags:
        tags.append("保持每日短练")
    return tags
