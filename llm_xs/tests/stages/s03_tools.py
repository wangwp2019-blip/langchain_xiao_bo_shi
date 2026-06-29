"""S3 · 工具层（离线）。"""

from __future__ import annotations


def run() -> None:
    from app.config import settings
    from app.knowledge import format_context, retrieve
    from app.tools import build_tools, calculator, get_today_info, search_knowledge_base

    assert "126" in calculator.invoke({"expression": "(25 + 17) * 3"})
    assert "32" in calculator.invoke({"expression": "2 ** 5"})
    bad = calculator.invoke({"expression": "__import__('os')"})
    assert "没看懂" in bad or "检查" in bad
    print("calculator: OK")

    today = get_today_info.invoke({})
    assert "星期" in today
    print("get_today_info:", today)

    tools = build_tools()
    names = [getattr(t, "name", str(t)) for t in tools]
    print("已装配工具:", names)
    assert "search_knowledge_base" in names
    assert "calculator" in names
    assert len(names) >= 7

    # 知识库工具：强制 keyword 后端，避免 S3 依赖 Embedding API
    from app.vector_store import get_vector_store

    settings.vector_backend = "keyword"
    get_vector_store.cache_clear()
    from app.knowledge import build_index

    build_index()
    ctx = search_knowledge_base.invoke({"query": "太阳系"})
    print("search_knowledge_base 输出长度:", len(ctx))
    assert isinstance(ctx, str) and len(ctx) > 10
    get_vector_store.cache_clear()

    print("Tavily Key:", "已配置" if settings.tavily_api_key else "未配置（降级）")
