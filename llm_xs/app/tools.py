"""Agent 工具集（生产级）。

1. RAG：``search_knowledge_base``
2. 联网：``tavily_search`` / ``google_search``（按配置启停，可并存）
3. 计算 / 日期
4. 长期记忆：``save_memory`` / ``recall_memories`` + profile 工具（治理：去重/容量/TTL）
"""

from __future__ import annotations

import ast
import operator
from datetime import datetime

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime

from .config import settings
from .knowledge import format_context, retrieve
from .memory_admin import list_memories, remember_fact, sweep_expired
from .safety import sanitize_output

# ==================== 1. 知识库检索（RAG）====================


@tool(parse_docstring=True)
def search_knowledge_base(query: str) -> str:
    """查询小博士内置的小学生百科知识库，获取与问题相关的课本资料。

    当小朋友的问题可能与语文、数学、科学、安全、健康、历史地理等课本知识相关时，
    应优先使用本工具，再结合检索到的资料作答。

    Args:
        query: 要在知识库中检索的问题或关键词
    """
    hits = retrieve(query)
    return format_context(hits)


# ==================== 数学计算 ====================

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](
            _safe_eval(node.left), _safe_eval(node.right)
        )
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("表达式中包含不支持的内容")


@tool(parse_docstring=True)
def calculator(expression: str) -> str:
    """做数学计算，支持加减乘除、乘方和括号。

    Args:
        expression: 数学表达式，只能包含数字和 + - * / % ** 以及括号
    """
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return f"{expression} = {result}"
    except Exception:  # noqa: BLE001
        return "这个算式我没看懂，只能算加减乘除、乘方和带括号的式子哦，再检查一下吧。"


@tool
def get_today_info() -> str:
    """获取今天的日期和星期，当小朋友问"今天几号""今天星期几"时使用。"""
    now = datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    return now.strftime("今天是 %Y年%m月%d日，") + weekdays[now.weekday()]


# ==================== 长期记忆（生产级治理）====================


def _student_id(runtime: ToolRuntime) -> str:
    try:
        return runtime.state.get("user_id") or "anonymous"
    except Exception:  # noqa: BLE001
        return "anonymous"


@tool(parse_docstring=True)
def save_student_profile(name: str, grade: str, runtime: ToolRuntime) -> str:
    """保存小朋友的基本资料（姓名、年级）到长期记忆。

    Args:
        name: 小朋友的名字
        grade: 小朋友的年级，例如"三年级"
        runtime: 工具运行时（自动注入）
    """
    sid = _student_id(runtime)
    from .memory_admin import save_profile

    save_profile(sid, name, grade)
    return f"已经记住啦：{name}，{grade}。"


@tool(parse_docstring=True)
def get_student_profile(runtime: ToolRuntime) -> str:
    """读取已保存的小朋友基本资料（姓名、年级）。

    Args:
        runtime: 工具运行时（自动注入）
    """
    sid = _student_id(runtime)
    item = runtime.store.get(("students", sid, "profile"), "info")
    if not item:
        return "我还不知道你的名字呢，可以先告诉我你叫什么、上几年级吗？"
    info = item.value
    return f"我记得你：{info.get('name', '小朋友')}，{info.get('grade', '')}。"


@tool(parse_docstring=True)
def save_memory(note: str, runtime: ToolRuntime) -> str:
    """记住关于小朋友的一条信息（兴趣、爱好、薄弱知识点等）到长期记忆。

    写入侧自动去重、容量上限与 TTL 治理。

    Args:
        note: 要记住的一句话信息
        runtime: 工具运行时（自动注入）
    """
    sid = _student_id(runtime)
    sweep_expired(sid)
    status = remember_fact(sid, note)
    if status == "duplicate":
        return "这条我记得啦，不用重复告诉我哦～"
    if status == "evicted_and_added":
        return "好的，我记住了！（旧的记忆太多，最旧的一条我先整理掉啦）"
    if status == "empty":
        return "你想让我记住什么呢？可以说具体一点哦。"
    return "好的，我记住了！"


@tool(parse_docstring=True)
def recall_memories(runtime: ToolRuntime) -> str:
    """回忆关于小朋友的所有已记住信息（资料 + 兴趣爱好等）。

    Args:
        runtime: 工具运行时（自动注入）
    """
    sid = _student_id(runtime)
    sweep_expired(sid)
    data = list_memories(sid)
    lines: list[str] = []
    if data.get("profile"):
        p = data["profile"]
        lines.append(f"资料：{p.get('name', '')} {p.get('grade', '')}".strip())
    for fact in data.get("facts") or []:
        val = fact.get("value") if isinstance(fact, dict) else None
        note = (val or {}).get("note") if isinstance(val, dict) else None
        if note:
            lines.append(f"- {note}")
    if not lines:
        return "我还没有记住关于你的信息哦。"
    return "我记得这些关于你的事情：\n" + "\n".join(lines)


# 规格别名（向后兼容旧教程命名）
remember_about_student = save_memory
recall_about_student = recall_memories


# ==================== 联网搜索（Tavily + Google，可并存）====================


def _sanitize_tool_text(text: str) -> str:
    """联网/RAG 工具输出净化（儿童安全）。"""
    return sanitize_output(str(text or ""))


def _build_tavily_search():
    if not settings.tavily_enabled:
        return None
    try:
        from langchain_tavily import TavilySearch

        base = TavilySearch(
            max_results=settings.web_search_max_results,
            tavily_api_key=settings.tavily_api_key,
        )

        @tool(parse_docstring=True)
        def tavily_search(query: str) -> str:
            """使用 Tavily 搜索最新公开信息（结果经儿童安全净化）。"""
            return _sanitize_tool_text(base.invoke({"query": query}))

        tavily_search.name = "tavily_search"
        return tavily_search
    except Exception:  # noqa: BLE001
        return None


def _build_google_search():
    if not settings.google_search_enabled:
        return None
    try:
        from langchain_google_community import GoogleSearchAPIWrapper

        wrapper = GoogleSearchAPIWrapper(
            google_api_key=settings.google_api_key,
            google_cse_id=settings.google_cse_id,
            k=settings.web_search_max_results,
        )

        @tool(parse_docstring=True)
        def google_search(query: str) -> str:
            """使用 Google 可编程搜索查找最新或课外的公开信息。

            当知识库没有答案、或需要最新新闻/事件时使用。

            Args:
                query: 搜索关键词
            """
            return _sanitize_tool_text(wrapper.run(query))

        return google_search
    except Exception:  # noqa: BLE001
        return None


def build_tools() -> list:
    """组装 Agent 工具列表（联网搜索按配置自动启停，可并存）。"""
    tools = [
        search_knowledge_base,
        calculator,
        get_today_info,
        save_student_profile,
        get_student_profile,
        save_memory,
        recall_memories,
    ]
    tavily = _build_tavily_search()
    if tavily is not None:
        tools.append(tavily)
    google = _build_google_search()
    if google is not None:
        tools.append(google)
    return tools
