"""家长同意、数据留存与隐私删除（合规层）。"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# 当前隐私政策版本（与 settings.consent_policy_version 同步）
POLICY_VERSION = settings.consent_policy_version

POLICY_TEXT = {
    "version": POLICY_VERSION,
    "title": "小博士儿童学习助手 · 家长知情同意与数据说明",
    "summary": (
        "本服务面向学龄儿童，需家长/监护人阅读并同意后方可使用在线功能。"
        "我们仅收集学习互动所必需的数据，不用于广告定向。"
    ),
    "data_collected": [
        "学习问答内容与练习记录（用于个性化辅导与审计）",
        "长期记忆偏好（可在设置中查看/清除）",
        "设备/IP 指纹（限流与安全，不含精确定位）",
    ],
    "retention": {
        "memory_ttl_days": "由 KIDS_MEMORY_TTL_DAYS 控制，0 表示不过期",
        "audit_retention_days": "由 KIDS_DATA_RETENTION_DAYS 控制 MySQL 对话/练习日志",
        "quiz_session_ttl_seconds": "出题会话一次性，默认 1 小时",
    },
    "parent_rights": [
        "GET /api/privacy/export — 导出孩子数据",
        "DELETE /api/privacy/account — 删除全部个人数据",
        "DELETE /api/memory — 清除长期记忆",
    ],
    "contact": "请联系学校或产品管理员处理合规请求",
}


def _consent_file() -> Path:
    path = settings.memory_dir / "parent_consent.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_file_consents() -> dict[str, dict[str, Any]]:
    path = _consent_file()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _save_file_consents(data: dict[str, dict[str, Any]]) -> None:
    _consent_file().write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_policy() -> dict[str, Any]:
    policy = dict(POLICY_TEXT)
    policy["version"] = settings.consent_policy_version
    policy["require_consent"] = settings.require_parent_consent
    policy["data_retention_days"] = settings.data_retention_days
    policy["memory_ttl_days"] = settings.memory_ttl_days
    return policy


def get_consent(user_id: str) -> dict[str, Any] | None:
    if settings.mysql_configured:
        try:
            from .mysql import ConsentRepository

            row = ConsentRepository().get(user_id)
            if row and not row.get("revoked_at"):
                return row
        except Exception as exc:  # noqa: BLE001
            logger.warning("MySQL 读取 consent 失败，回退文件: %s", exc)

    with _lock:
        row = _load_file_consents().get(user_id)
    if row and row.get("revoked_at"):
        return None
    return row


def has_valid_consent(user_id: str) -> bool:
    if not settings.require_parent_consent:
        return True
    row = get_consent(user_id)
    if not row:
        return False
    version = row.get("consent_version") or row.get("policy_version")
    return version == settings.consent_policy_version and not row.get("revoked_at")


def record_consent(
    user_id: str,
    *,
    parent_name: str,
    parent_email: str | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    record: dict[str, Any] = {
        "user_id": user_id,
        "parent_name": parent_name.strip()[:64],
        "parent_email": (parent_email or "").strip()[:128] or None,
        "consent_version": settings.consent_policy_version,
        "granted_at": now.isoformat(),
        "ip_address": ip_address,
        "revoked_at": None,
    }

    if settings.mysql_configured:
        try:
            from .mysql import ConsentRepository

            ConsentRepository().upsert(
                user_id=user_id,
                parent_name=record["parent_name"],
                parent_email=record["parent_email"],
                consent_version=record["consent_version"],
                ip_address=ip_address,
            )
            return ConsentRepository().get(user_id) or record
        except Exception as exc:  # noqa: BLE001
            logger.warning("MySQL 写入 consent 失败，回退文件: %s", exc)

    with _lock:
        data = _load_file_consents()
        data[user_id] = record
        _save_file_consents(data)
    return record


def revoke_consent(user_id: str) -> bool:
    if settings.mysql_configured:
        try:
            from .mysql import ConsentRepository

            return ConsentRepository().revoke(user_id) > 0
        except Exception as exc:  # noqa: BLE001
            logger.warning("MySQL revoke consent 失败: %s", exc)

    with _lock:
        data = _load_file_consents()
        if user_id not in data:
            return False
        data[user_id]["revoked_at"] = datetime.now(timezone.utc).isoformat()
        _save_file_consents(data)
    return True


def delete_all_user_data(user_id: str) -> dict[str, Any]:
    """删除用户全部可识别数据（记忆 + MySQL 审计 + consent）。"""
    from .memory_admin import clear_memories

    result: dict[str, Any] = {"user_id": user_id, "memory_removed": 0}

    result["memory_removed"] = clear_memories(user_id)
    revoke_consent(user_id)

    if settings.mysql_configured:
        try:
            from .mysql import ChatLogRepository, ConsentRepository, QuizRecordRepository

            result["chat_logs_deleted"] = ChatLogRepository().delete_by_user(user_id)
            result["quiz_records_deleted"] = QuizRecordRepository().delete_by_user(user_id)
            ConsentRepository().delete(user_id)
        except Exception as exc:  # noqa: BLE001
            result["mysql_error"] = str(exc)

    with _lock:
        data = _load_file_consents()
        if user_id in data:
            del data[user_id]
            _save_file_consents(data)

    return result


def sweep_expired_audit_data() -> dict[str, Any]:
    """按 KIDS_DATA_RETENTION_DAYS 清理 MySQL 审计数据。"""
    days = settings.data_retention_days
    if days <= 0:
        return {"skipped": True, "reason": "KIDS_DATA_RETENTION_DAYS=0 不自动清理"}

    if not settings.mysql_configured:
        return {"skipped": True, "reason": "未配置 MySQL"}

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    try:
        from .mysql import ChatLogRepository, QuizRecordRepository

        chat_n = ChatLogRepository().delete_older_than(cutoff)
        quiz_n = QuizRecordRepository().delete_older_than(cutoff)
        logger.info("数据留存清理: chat=%d quiz=%d cutoff=%s", chat_n, quiz_n, cutoff.isoformat())
        return {
            "cutoff": cutoff.isoformat(),
            "retention_days": days,
            "chat_logs_deleted": chat_n,
            "quiz_records_deleted": quiz_n,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("数据留存清理失败")
        return {"error": str(exc)}


def consent_denied_message() -> str:
    return (
        "小朋友，使用前需要家长/监护人阅读并同意《隐私与数据说明》哦～"
        "请让家长打开页面完成同意后再试。🌈"
    )


def clear_consents_for_tests() -> None:
    """测试隔离：清空文件 consent 存储。"""
    path = _consent_file()
    if path.is_file():
        path.unlink(missing_ok=True)
