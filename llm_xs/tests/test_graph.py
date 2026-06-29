"""S4 · LangGraph 图结构与路由。"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END
from langgraph.prebuilt import tools_condition

from app.graph.builder import build_kids_graph
from app.graph.nodes import _ensure_system_message
from app.graph.prompts import KIDS_SYSTEM_PROMPT
from app.graph.study_card_graph import build_study_card_graph


def test_kids_graph_nodes():
    graph = build_kids_graph()
    nodes = set(graph.get_graph().nodes.keys())
    assert {"call_model", "tools", "__start__", "__end__"}.issubset(nodes)
    assert graph.checkpointer is not None
    assert graph.store is not None


def test_study_card_graph_nodes():
    sc = build_study_card_graph()
    sn = set(sc.get_graph().nodes.keys())
    assert {"retrieve_context", "generate_card_json"}.issubset(sn)


def test_tools_condition_routing():
    assert (
        tools_condition(
            {
                "messages": [
                    HumanMessage("算"),
                    AIMessage(content="", tool_calls=[{"name": "calculator", "args": {}, "id": "1"}]),
                ]
            }
        )
        == "tools"
    )
    assert (
        tools_condition({"messages": [HumanMessage("你好"), AIMessage(content="你好呀")]})
        == END
    )


def test_system_message_injection():
    msgs = _ensure_system_message([HumanMessage("你好")])
    assert isinstance(msgs[0], SystemMessage)
    assert msgs[0].content == KIDS_SYSTEM_PROMPT

    existing = [SystemMessage(content="custom"), HumanMessage("hi")]
    assert _ensure_system_message(existing)[0].content == "custom"
