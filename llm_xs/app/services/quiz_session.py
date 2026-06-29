"""出题会话：服务端保存题目与答案，判分仅接受 session_id（防客户端伪造）。"""

from __future__ import annotations

from ..domain import Quiz
from .quiz_session_store import get_quiz_session_store, reset_quiz_session_store


def create_session(principal: str, quiz: Quiz) -> str:
    return get_quiz_session_store().create(principal, quiz)


def consume_session(session_id: str, principal: str) -> Quiz | None:
    return get_quiz_session_store().consume(session_id, principal)


def clear_sessions_for_tests() -> None:
    reset_quiz_session_store()
