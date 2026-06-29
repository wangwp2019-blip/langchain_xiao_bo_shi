"""S5 · RAG 在线链路 + 图节点（离线，keyword 后端不需 Embedding）。"""

from __future__ import annotations


def run() -> None:
    from app.config import settings
    from app.knowledge import build_index, format_context, retrieve
    from app.graph.nodes import retrieve_context
    from app.vector_store import get_vector_store

    # 强制 keyword（settings 已加载，直接改字段并清缓存）
    settings.vector_backend = "keyword"
    get_vector_store.cache_clear()

    n = build_index()
    print(f"keyword 建索引: {n} 个片段")
    assert n > 0

    hits = retrieve("太阳系有几大行星")
    print(f"检索命中: {len(hits)} 条，top score={hits[0]['score']:.3f}")
    assert hits, "检索结果为空"
    assert any("行星" in h["text"] for h in hits)

    # 学习卡片子图 · retrieve_context 节点
    from app.graph.nodes import retrieve_context

    out = retrieve_context({"question": "太阳系有几大行星？"})
    assert "context" in out and len(out["context"]) > 20
    print("retrieve_context 节点输出预览:", out["context"][:80].replace("\n", " ") + "…")

    # format_context
    ctx = format_context(hits[:2])
    assert "资料" in ctx
    print("format_context OK")

    get_vector_store.cache_clear()
