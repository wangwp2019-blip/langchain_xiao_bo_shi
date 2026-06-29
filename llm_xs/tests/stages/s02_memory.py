"""S2 · 记忆系统（离线）。"""

from __future__ import annotations


def run() -> None:
    from app import config
    from app.db import close_pool
    from app.long_term_memory import FileBackedStore, get_store
    from app.short_term_memory import get_checkpointer

    # 长期记忆：文件落盘 + 重启恢复
    mem = config.settings.memory_dir / "_stage2_store.json"
    mem.unlink(missing_ok=True)
    s1 = FileBackedStore(mem)
    s1.put(("students", "stu1", "profile"), "info", {"name": "小明", "grade": "三年级"})
    s1.put(("students", "stu1", "facts"), "fact-1", {"note": "喜欢恐龙"})
    assert mem.exists()

    s2 = FileBackedStore(mem)
    got = s2.get(("students", "stu1", "profile"), "info")
    facts = [it.value["note"] for it in s2.search(("students", "stu1", "facts"))]
    print("长期记忆重启恢复:", got.value if got else None, facts)
    assert got and got.value["name"] == "小明"
    assert facts == ["喜欢恐龙"]
    mem.unlink(missing_ok=True)

    # 短期记忆 checkpointer 可获取
    cp = get_checkpointer()
    print("checkpointer 类型:", type(cp).__name__)
    assert cp is not None

    # store 单例
    store = get_store()
    print("长期 store 类型:", type(store).__name__)
    assert store is not None

    # 连接池优雅关闭（未用 postgres 时幂等）
    close_pool()
    print("close_pool 幂等 OK")
