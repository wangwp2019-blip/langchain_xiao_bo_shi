"""长期记忆（跨会话）：基于 LangGraph 的 ``store``。

后端通过 ``KIDS_MEMORY_BACKEND`` 切换：

- ``file``（默认）：``FileBackedStore``，在 ``InMemoryStore`` 基础上把每次写入
  持久化到 JSON 文件，进程重启后仍能记住学生信息（真正的"长期存储"），且零额外依赖。
- ``memory``：教程同款 ``InMemoryStore``，进程结束即丢失（仅用于演示）。
- ``postgres``：``PostgresStore`` + **连接池**（生产级），工业级持久化，
  与短期记忆共用连接池，需要 psycopg 与可用的 PostgreSQL。

无论哪种后端，对外都是标准的 LangGraph store，工具里通过 ``ToolRuntime.store`` 访问。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from langgraph.store.memory import InMemoryStore

from .config import settings

_NS_SEP = "\x1f"  # 用于把 namespace 元组拼成持久化的字符串 key


class FileBackedStore(InMemoryStore):
    """在 InMemoryStore 基础上增加 JSON 文件持久化。

    继承自 ``InMemoryStore``，因此 ``get`` / ``search`` 等接口与教程完全一致；
    仅重写 ``put``，在写入内存的同时把数据落盘，实现重启不丢。
    """

    def __init__(self, path: str | Path):
        super().__init__()
        self._path = Path(path)
        self._mirror: dict[str, dict[str, Any]] = {}
        self._restore()

    def _ns_key(self, namespace: tuple[str, ...]) -> str:
        return _NS_SEP.join(namespace)

    def _restore(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for ns_str, kv in raw.items():
            namespace = tuple(ns_str.split(_NS_SEP))
            for key, value in kv.items():
                super().put(namespace, key, value)
                self._mirror.setdefault(ns_str, {})[key] = value

    def put(self, namespace, key, value, *args, **kwargs):  # type: ignore[override]
        super().put(namespace, key, value, *args, **kwargs)
        self._mirror.setdefault(self._ns_key(namespace), {})[key] = value
        self._flush()

    def delete(self, namespace, key, *args, **kwargs):  # type: ignore[override]
        super().delete(namespace, key, *args, **kwargs)
        ns = self._ns_key(namespace)
        bucket = self._mirror.get(ns)
        if bucket and key in bucket:
            del bucket[key]
            if not bucket:
                self._mirror.pop(ns, None)
            self._flush()

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._mirror, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _get_postgres_store():
    """生产级 PostgreSQL 长期记忆后端：基于共享连接池。

    与短期记忆同理，旧写法手动 ``__enter__()`` 会泄漏连接、绕过连接池。
    这里改为把 ``app.db.get_pool()`` 的连接池交给 ``PostgresStore``，
    与短期记忆**共用同一个连接池**，生命周期由 ``close_pool()`` 统一管理。

    ``setup()`` 会自动建好 store 所需的表（幂等，可重复调用）。
    """
    from langgraph.store.postgres import PostgresStore

    from .db import get_pool

    store = PostgresStore(get_pool())
    store.setup()
    return store


@lru_cache(maxsize=1)
def get_store():
    """根据配置返回长期记忆 store（单例）。"""
    backend = settings.memory_backend.lower()
    if backend == "postgres":
        return _get_postgres_store()
    if backend == "memory":
        return InMemoryStore()
    settings.ensure_dirs()
    return FileBackedStore(settings.long_term_store_file)
