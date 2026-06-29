"""S2 · 长期/短期记忆与治理。"""

from __future__ import annotations

import app.config as cfg
from app.db import close_pool
from app.long_term_memory import FileBackedStore, get_store
from app.memory_admin import clear_memories, list_memories, remember_fact, sweep_expired
from app.short_term_memory import get_checkpointer


def test_file_backed_store_persistence(tmp_path):
    path = tmp_path / "store.json"
    s1 = FileBackedStore(path)
    s1.put(("students", "stu1", "profile"), "info", {"name": "小明", "grade": "三年级"})
    s1.put(("students", "stu1", "facts"), "fact-1", {"note": "喜欢恐龙"})
    assert path.exists()

    s2 = FileBackedStore(path)
    got = s2.get(("students", "stu1", "profile"), "info")
    facts = [it.value["note"] for it in s2.search(("students", "stu1", "facts"))]
    assert got.value["name"] == "小明"
    assert facts == ["喜欢恐龙"]


def test_checkpointer_available():
    cp = get_checkpointer()
    assert cp is not None


def test_get_store_singleton():
    assert get_store() is not None


def test_remember_fact_eviction(monkeypatch):
    import uuid

    original = cfg.settings.memory_max_items
    monkeypatch.setattr(cfg.settings, "memory_max_items", 2)
    uid = f"pytest-evict-{uuid.uuid4().hex[:8]}"
    clear_memories(uid)
    try:
        remember_fact(uid, "第一条")
        remember_fact(uid, "第二条")
        status = remember_fact(uid, "第三条")
        assert status == "evicted_and_added"
        assert len(list_memories(uid)["facts"]) == 2
    finally:
        cfg.settings.memory_max_items = original
        clear_memories(uid)


def test_sweep_expired_noop_when_ttl_disabled():
    uid = "pytest-sweep-user"
    clear_memories(uid)
    remember_fact(uid, "不会过期")
    assert sweep_expired(uid) == 0
    clear_memories(uid)


def test_close_pool_idempotent():
    from app.mysql_db import close_mysql_pool

    close_pool()
    close_mysql_pool()
    close_pool()
    close_mysql_pool()
