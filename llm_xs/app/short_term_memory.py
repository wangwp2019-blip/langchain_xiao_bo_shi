"""短期记忆（单次会话/对话 thread）：基于 LangGraph 的 ``checkpointer``。

后端通过 ``KIDS_SHORT_TERM_BACKEND`` 切换：

- ``memory``（默认）：``InMemorySaver``，进程结束即丢失。
- ``sqlite``：``SqliteSaver``，单文件持久化，适合单机生产 / 开发。
- ``postgres``：``PostgresSaver`` + 连接池，多 worker 生产推荐。
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.checkpoint.memory import InMemorySaver

from .config import settings


def _get_postgres_saver():
    from langgraph.checkpoint.postgres import PostgresSaver

    from .db import get_pool

    saver = PostgresSaver(get_pool())
    saver.setup()
    return saver


def _get_sqlite_saver():
    import sqlite3

    from langgraph.checkpoint.sqlite import SqliteSaver

    settings.ensure_dirs()
    conn = sqlite3.connect(str(settings.sqlite_checkpoint_path), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


@lru_cache(maxsize=1)
def get_checkpointer():
    """根据配置返回短期记忆 checkpointer（单例）。"""
    backend = settings.short_term_backend.lower()
    if backend == "postgres":
        return _get_postgres_saver()
    if backend == "sqlite":
        return _get_sqlite_saver()
    return InMemorySaver()
