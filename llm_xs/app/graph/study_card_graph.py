"""学习卡片子图：显式三步流水线（retrieve → generate → END）。

与主对话图分离的原因
--------------------
1. 学习卡片不需要 tool 循环，单独小图更清晰；
2. 可在 LangGraph Studio 里单独调试 RAG + 结构化输出；
3. 演示「一个项目多个 StateGraph」的组织方式。
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from .nodes import generate_card_json, retrieve_context
from .state import StudyCardGraphState


def build_study_card_graph():
    builder = StateGraph(StudyCardGraphState)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("generate_card_json", generate_card_json)
    builder.add_edge(START, "retrieve_context")
    builder.add_edge("retrieve_context", "generate_card_json")
    builder.add_edge("generate_card_json", END)
    return builder.compile()


@lru_cache(maxsize=1)
def get_study_card_graph():
    return build_study_card_graph()
