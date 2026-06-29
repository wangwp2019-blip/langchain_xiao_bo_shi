"""MySQL Repository 预留实现（用户资料 / 对话日志 / 练习记录）。

后续可在此扩展：
- 与 LangGraph Store 双写同步
- 家长端学习报告
- 运营后台统计
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..mysql_db import execute, fetch_all, fetch_one, mysql_connection


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserProfileRepository:
    """``kids_user_profiles`` — 用户基本资料（可与长期记忆 profile 同步）。"""

    TABLE = "kids_user_profiles"

    def upsert(self, user_id: str, name: str, grade: str, extra: dict | None = None) -> int:
        payload = json.dumps(extra or {}, ensure_ascii=False)
        return execute(
            f"""
            INSERT INTO {self.TABLE} (user_id, name, grade, extra_json, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                grade = VALUES(grade),
                extra_json = VALUES(extra_json),
                updated_at = VALUES(updated_at)
            """,
            (user_id, name, grade, payload, _utc_now()),
        )

    def get(self, user_id: str) -> dict[str, Any] | None:
        return fetch_one(
            f"SELECT user_id, name, grade, extra_json, created_at, updated_at "
            f"FROM {self.TABLE} WHERE user_id = %s",
            (user_id,),
        )


class ChatLogRepository:
    """``kids_chat_logs`` — 对话审计 / 分析（不含敏感原文时可仅存摘要）。"""

    TABLE = "kids_chat_logs"

    def append(
        self,
        *,
        user_id: str,
        thread_id: str,
        question: str,
        answer: str,
        mode: str = "offline",
        request_id: str | None = None,
    ) -> int:
        return execute(
            f"""
            INSERT INTO {self.TABLE}
                (user_id, thread_id, question, answer, mode, request_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, thread_id, question, answer, mode, request_id, _utc_now()),
        )

    def list_recent(self, user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(100, limit))
        return fetch_all(
            f"""
            SELECT id, user_id, thread_id, question, answer, mode, request_id, created_at
            FROM {self.TABLE}
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT {limit}
            """,
            (user_id,),
        )

    def delete_by_user(self, user_id: str) -> int:
        return execute(f"DELETE FROM {self.TABLE} WHERE user_id = %s", (user_id,))

    def delete_older_than(self, cutoff: datetime) -> int:
        return execute(
            f"DELETE FROM {self.TABLE} WHERE created_at < %s",
            (cutoff,),
        )


class QuizRecordRepository:
    """``kids_quiz_records`` — 练习记录与得分。"""

    TABLE = "kids_quiz_records"

    def save(
        self,
        *,
        user_id: str,
        grade: str,
        subject: str,
        total: int,
        correct: int,
        score: int,
        detail_json: dict | None = None,
    ) -> int:
        payload = json.dumps(detail_json or {}, ensure_ascii=False)
        return execute(
            f"""
            INSERT INTO {self.TABLE}
                (user_id, grade, subject, total, correct, score, detail_json, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, grade, subject, total, correct, score, payload, _utc_now()),
        )

    def list_by_user(self, user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(100, limit))
        return fetch_all(
            f"""
            SELECT id, user_id, grade, subject, total, correct, score, created_at
            FROM {self.TABLE}
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT {limit}
            """,
            (user_id,),
        )

    def delete_by_user(self, user_id: str) -> int:
        return execute(f"DELETE FROM {self.TABLE} WHERE user_id = %s", (user_id,))

    def delete_older_than(self, cutoff: datetime) -> int:
        return execute(
            f"DELETE FROM {self.TABLE} WHERE created_at < %s",
            (cutoff,),
        )


class QuizSessionRepository:
    """``kids_quiz_sessions`` — 出题会话（含答案，判分前服务端暂存）。"""

    TABLE = "kids_quiz_sessions"

    def insert(
        self,
        *,
        session_id: str,
        principal: str,
        quiz_json: dict,
        expires_at: datetime,
    ) -> int:
        payload = json.dumps(quiz_json, ensure_ascii=False)
        return execute(
            f"""
            INSERT INTO {self.TABLE}
                (session_id, principal, quiz_json, expires_at, consumed_at, created_at)
            VALUES (%s, %s, %s, %s, NULL, %s)
            """,
            (session_id, principal, payload, expires_at, _utc_now()),
        )

    def consume(self, session_id: str, principal: str) -> dict | None:
        """原子消费：principal 不匹配时不标记 consumed（防恶意消耗）。"""
        now = _utc_now()
        with mysql_connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT principal, quiz_json, expires_at, consumed_at
                        FROM {self.TABLE}
                        WHERE session_id = %s
                        FOR UPDATE
                        """,
                        (session_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        conn.rollback()
                        return None
                    if row.get("consumed_at") is not None:
                        conn.rollback()
                        return None
                    expires = row["expires_at"]
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=timezone.utc)
                    if expires <= now:
                        conn.rollback()
                        return None
                    if row["principal"] != principal:
                        conn.rollback()
                        return None
                    cur.execute(
                        f"""
                        UPDATE {self.TABLE}
                        SET consumed_at = %s
                        WHERE session_id = %s
                        """,
                        (now, session_id),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        raw = row["quiz_json"]
        if isinstance(raw, str):
            return json.loads(raw)
        return dict(raw)

    def delete_expired(self) -> int:
        return execute(
            f"DELETE FROM {self.TABLE} WHERE expires_at < %s OR consumed_at IS NOT NULL",
            (_utc_now(),),
        )

    def clear_all(self) -> int:
        return execute(f"DELETE FROM {self.TABLE}")


class ConsentRepository:
    """``kids_parent_consent`` — 家长知情同意记录。"""

    TABLE = "kids_parent_consent"

    def upsert(
        self,
        *,
        user_id: str,
        parent_name: str,
        consent_version: str,
        parent_email: str | None = None,
        ip_address: str | None = None,
    ) -> int:
        now = _utc_now()
        return execute(
            f"""
            INSERT INTO {self.TABLE}
                (user_id, parent_name, parent_email, consent_version, granted_at, ip_address, revoked_at)
            VALUES (%s, %s, %s, %s, %s, %s, NULL)
            ON DUPLICATE KEY UPDATE
                parent_name = VALUES(parent_name),
                parent_email = VALUES(parent_email),
                consent_version = VALUES(consent_version),
                granted_at = VALUES(granted_at),
                ip_address = VALUES(ip_address),
                revoked_at = NULL
            """,
            (user_id, parent_name, parent_email, consent_version, now, ip_address),
        )

    def get(self, user_id: str) -> dict[str, Any] | None:
        return fetch_one(
            f"""
            SELECT user_id, parent_name, parent_email, consent_version,
                   granted_at, ip_address, revoked_at
            FROM {self.TABLE} WHERE user_id = %s
            """,
            (user_id,),
        )

    def revoke(self, user_id: str) -> int:
        return execute(
            f"UPDATE {self.TABLE} SET revoked_at = %s WHERE user_id = %s AND revoked_at IS NULL",
            (_utc_now(), user_id),
        )

    def delete(self, user_id: str) -> int:
        return execute(f"DELETE FROM {self.TABLE} WHERE user_id = %s", (user_id,))
