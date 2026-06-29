"""可选 MySQL 业务审计落库（chat / quiz），失败不影响主路径。"""

from __future__ import annotations

import logging

from .config import settings

logger = logging.getLogger(__name__)

_audit_write_failures = 0


def audit_write_failures() -> int:
    return _audit_write_failures


def persist_chat_log(
    *,
    user_id: str,
    thread_id: str,
    question: str,
    answer: str,
    mode: str,
    request_id: str | None = None,
) -> None:
    if not settings.mysql_configured or not settings.mysql_audit_enabled:
        return
    try:
        from .mysql import ChatLogRepository

        ChatLogRepository().append(
            user_id=user_id,
            thread_id=thread_id,
            question=question[:2000],
            answer=answer[:4000],
            mode=mode,
            request_id=request_id,
        )
    except Exception as exc:  # noqa: BLE001
        global _audit_write_failures
        _audit_write_failures += 1
        try:
            from . import metrics

            metrics.record_audit_failure()
        except Exception:
            pass
        logger.warning("MySQL 对话审计写入失败（忽略）: %s", exc)


def persist_quiz_record(
    *,
    user_id: str,
    grade: str,
    subject: str,
    total: int,
    correct: int,
    score: int,
    detail_json: dict | None = None,
) -> None:
    if not settings.mysql_configured or not settings.mysql_audit_enabled:
        return
    try:
        from .mysql import QuizRecordRepository

        QuizRecordRepository().save(
            user_id=user_id,
            grade=grade,
            subject=subject,
            total=total,
            correct=correct,
            score=score,
            detail_json=detail_json,
        )
    except Exception as exc:  # noqa: BLE001
        global _audit_write_failures
        _audit_write_failures += 1
        try:
            from . import metrics

            metrics.record_audit_failure()
        except Exception:
            pass
        logger.warning("MySQL 练习记录写入失败（忽略）: %s", exc)
