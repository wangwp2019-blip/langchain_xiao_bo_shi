"""MySQL 业务 Repository 层（预留，后续按需扩展）。

当前提供示例 Repository，演示如何基于 ``app.mysql_db`` 读写预留表。
未配置 MySQL 时调用会抛出 ``RuntimeError``（与 PostgreSQL 池行为一致）。
"""

from .repository import (
    ChatLogRepository,
    ConsentRepository,
    QuizRecordRepository,
    QuizSessionRepository,
    UserProfileRepository,
)

__all__ = [
    "UserProfileRepository",
    "ChatLogRepository",
    "QuizRecordRepository",
    "QuizSessionRepository",
    "ConsentRepository",
]
