"""长期记忆治理与合规：查看 / 清除 / 去重 / 容量上限 / TTL。

直接操作 LangGraph store（``long_term_memory.get_store()``），命名空间约定与
``tools.py`` 一致：``("students", user_id, "profile" | "facts")``。

合规能力：
- 查看：列出某 user_id 的全部长期记忆。
- 清除：删除某 user_id 的全部长期记忆。
- 治理：写入侧内容去重、容量上限（超限淘汰最旧）、TTL 过期清理。
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta

from .config import settings
from .long_term_memory import get_store

logger = logging.getLogger(__name__)

_NS_ROOT = "students"
_FACTS = "facts"
_PROFILE = "profile"


def _facts_ns(user_id: str) -> tuple[str, str, str]:
    return (_NS_ROOT, user_id, _FACTS)


def _profile_ns(user_id: str) -> tuple[str, str, str]:
    return (_NS_ROOT, user_id, _PROFILE)


def list_memories(user_id: str) -> dict:
    """返回某用户的长期记忆（资料 + 事实列表 + 治理元数据）。"""
    sweep_expired(user_id)
    store = get_store()
    profile_item = store.get(_profile_ns(user_id), "info")
    profile = profile_item.value if profile_item else None

    facts = []
    for item in store.search(_facts_ns(user_id)):
        facts.append({"key": item.key, "value": item.value})
    return {
        "user_id": user_id,
        "profile": profile,
        "facts": facts,
        "governance": {
            "max_items": settings.memory_max_items,
            "ttl_days": settings.memory_ttl_days,
            "fact_count": len(facts),
        },
    }


def save_profile(user_id: str, name: str, grade: str) -> None:
    """写入用户资料（与 tools.save_student_profile 共用治理路径）。"""
    store = get_store()
    store.put(
        _profile_ns(user_id),
        "info",
        {"name": (name or "").strip(), "grade": (grade or "").strip()},
    )


def clear_memories(user_id: str) -> int:
    """清除某用户全部长期记忆，返回删除条数。"""
    store = get_store()
    removed = 0

    if store.get(_profile_ns(user_id), "info"):
        store.delete(_profile_ns(user_id), "info")
        removed += 1

    for item in list(store.search(_facts_ns(user_id))):
        store.delete(_facts_ns(user_id), item.key)
        removed += 1
    logger.info("已清除用户 %s 的 %d 条长期记忆", user_id, removed)
    return removed


def _content_hash(note: str) -> str:
    return hashlib.sha256(note.strip().encode("utf-8")).hexdigest()[:16]


def remember_fact(user_id: str, note: str) -> str:
    """治理化写入一条事实：去重 + 容量上限 + 打时间戳。

    返回："added" / "duplicate" / "evicted_and_added"。
    """
    note = (note or "").strip()
    if not note:
        return "empty"
    store = get_store()
    ns = _facts_ns(user_id)
    existing = list(store.search(ns))

    new_hash = _content_hash(note)
    for item in existing:
        val = item.value if isinstance(item.value, dict) else {}
        if val.get("hash") == new_hash:
            return "duplicate"

    status = "added"
    max_items = settings.memory_max_items
    if max_items > 0 and len(existing) >= max_items:
        oldest = min(existing, key=lambda it: (it.value or {}).get("time", ""))
        store.delete(ns, oldest.key)
        status = "evicted_and_added"

    key = f"fact-{_content_hash(note + datetime.now().isoformat())}"
    store.put(
        ns,
        key,
        {
            "note": note,
            "hash": new_hash,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    return status


def sweep_expired(user_id: str) -> int:
    """清理超过 TTL 的事实，返回清理条数（TTL<=0 表示不过期）。"""
    days = settings.memory_ttl_days
    if days <= 0:
        return 0
    store = get_store()
    ns = _facts_ns(user_id)
    cutoff = datetime.now() - timedelta(days=days)
    removed = 0
    for item in list(store.search(ns)):
        ts = (item.value or {}).get("time", "")
        try:
            when = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            continue
        if when < cutoff:
            store.delete(ns, item.key)
            removed += 1
    return removed
