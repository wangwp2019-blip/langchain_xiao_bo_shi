"""LangGraph 图编译：显式 StateGraph + checkpointer + store。

图结构（ReAct 循环，与 ``create_agent`` 内部逻辑等价，但**完全可见**）::

    START → call_model → tools_condition?
                              ├─ tools → call_model  （有 tool_calls 时循环）
                              └─ END                   （无 tool_calls 时结束）

编译参数
--------
- ``checkpointer``：短期记忆（同一 ``thread_id`` 多轮对话）。
- ``store``：长期记忆（``ToolRuntime.store`` 注入给记忆类工具）。

这两者在 ``compile()`` 时传入，是 LangGraph 持久化能力的核心入口。
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from ..long_term_memory import get_store
from ..short_term_memory import get_checkpointer
from ..tools import build_tools
from .nodes import call_model
from .state import KidsGraphState


def build_kids_graph():
    """构建并编译主对话 StateGraph（不缓存，便于测试替换依赖）。"""
    tools = build_tools()
    tool_node = ToolNode(tools)

    builder = StateGraph(KidsGraphState)
    builder.add_node("call_model", call_model)
    builder.add_node("tools", tool_node)

    builder.add_edge(START, "call_model")
    builder.add_conditional_edges(
        "call_model",
        tools_condition,
        {"tools": "tools", END: END},
    )
    builder.add_edge("tools", "call_model")

    return builder.compile(
        checkpointer=get_checkpointer(),
        store=get_store(),
    )


@lru_cache(maxsize=1)
def get_kids_graph():
    """返回编译完成的主对话图（单例）。"""
    return build_kids_graph()
