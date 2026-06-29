"""S3 · 工具层（calculator / 日期 / 知识库 / 装配）。"""

from __future__ import annotations

from app.knowledge import build_index
from app.tools import build_tools, calculator, get_today_info, search_knowledge_base


def test_calculator_basic():
    assert "126" in calculator.invoke({"expression": "(25 + 17) * 3"})
    assert "32" in calculator.invoke({"expression": "2 ** 5"})


def test_calculator_rejects_unsafe():
    bad = calculator.invoke({"expression": "__import__('os')"})
    assert "没看懂" in bad or "检查" in bad


def test_get_today_info():
    today = get_today_info.invoke({})
    assert "星期" in today
    assert "年" in today


def test_build_tools_core_names():
    tools = build_tools()
    names = [getattr(t, "name", str(t)) for t in tools]
    expected = {
        "search_knowledge_base",
        "calculator",
        "get_today_info",
        "save_student_profile",
        "get_student_profile",
        "save_memory",
        "recall_memories",
    }
    assert expected.issubset(set(names))
    assert len(names) >= 7


def test_search_knowledge_base(keyword_backend):
    build_index()
    ctx = search_knowledge_base.invoke({"query": "太阳系"})
    assert isinstance(ctx, str)
    assert len(ctx) > 10
