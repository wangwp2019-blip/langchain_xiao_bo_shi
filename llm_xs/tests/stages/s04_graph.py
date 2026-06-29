"""S4 · LangGraph 图结构（离线）。"""

from __future__ import annotations


def run() -> None:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from langgraph.graph import END
    from langgraph.prebuilt import tools_condition

    from app.graph.builder import build_kids_graph
    from app.graph.nodes import _ensure_system_message
    from app.graph.prompts import KIDS_SYSTEM_PROMPT
    from app.graph.study_card_graph import build_study_card_graph

    # 主对话图
    graph = build_kids_graph()
    nodes = set(graph.get_graph().nodes.keys())
    print("主图节点:", sorted(nodes))
    assert {"call_model", "tools", "__start__", "__end__"}.issubset(nodes)

    # 学习卡片子图
    sc = build_study_card_graph()
    sn = set(sc.get_graph().nodes.keys())
    print("学习卡片子图节点:", sorted(sn))
    assert {"retrieve_context", "generate_card_json"}.issubset(sn)

    # tools_condition 路由
    assert tools_condition(
        {
            "messages": [
                HumanMessage("算"),
                AIMessage(content="", tool_calls=[{"name": "calculator", "args": {}, "id": "1"}]),
            ]
        }
    ) == "tools"
    assert tools_condition(
        {"messages": [HumanMessage("你好"), AIMessage(content="你好呀")]}
    ) == END
    print("tools_condition 路由 OK")

    # System Prompt 注入
    msgs = _ensure_system_message([HumanMessage("你好")])
    assert isinstance(msgs[0], SystemMessage)
    assert msgs[0].content == KIDS_SYSTEM_PROMPT
    print("System Prompt 首轮注入 OK")

    # compile 带 checkpointer + store
    assert graph.checkpointer is not None
    assert graph.store is not None
    print("compile(checkpointer, store) 已注入")
