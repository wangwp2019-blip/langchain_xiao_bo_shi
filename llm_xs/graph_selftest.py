"""LangGraph 图结构离线自测（不调用外部 API）。

验证：
1. 主对话图节点/边是否正确编译
2. 学习卡片子图结构
3. tools_condition 路由逻辑（mock AIMessage with/without tool_calls）
"""

from __future__ import annotations


def section(title: str) -> None:
    print("\n" + "=" * 52 + "\n" + title + "\n" + "=" * 52)


def main() -> None:
    section("[1] 主对话图：编译与拓扑")
    from app.graph.builder import build_kids_graph

    graph = build_kids_graph()
    g = graph.get_graph()
    nodes = set(g.nodes.keys())
    print("节点:", sorted(nodes))
    assert "call_model" in nodes and "tools" in nodes
    print("主对话图编译 OK")

    section("[2] 学习卡片子图：编译与拓扑")
    from app.graph.study_card_graph import build_study_card_graph

    sc = build_study_card_graph()
    sg = sc.get_graph()
    sn = set(sg.nodes.keys())
    print("节点:", sorted(sn))
    assert "retrieve_context" in sn and "generate_card_json" in sn
    print("学习卡片子图编译 OK")

    section("[3] tools_condition 路由")
    from langchain_core.messages import AIMessage, HumanMessage
    from langgraph.graph import END
    from langgraph.prebuilt import tools_condition

    state_with_tools = {
        "messages": [
            HumanMessage("算 1+1"),
            AIMessage(content="", tool_calls=[{"name": "calculator", "args": {"expression": "1+1"}, "id": "1"}]),
        ]
    }
    state_no_tools = {"messages": [HumanMessage("你好"), AIMessage(content="你好呀")]}
    assert tools_condition(state_with_tools) == "tools"
    assert tools_condition(state_no_tools) == END
    print("有 tool_calls → tools；无 tool_calls → END  OK")

    section("[4] call_model 节点：System Prompt 注入逻辑")
    from app.graph.nodes import _ensure_system_message
    from app.graph.prompts import KIDS_SYSTEM_PROMPT

    msgs = _ensure_system_message([HumanMessage("你好")])
    assert msgs[0].content == KIDS_SYSTEM_PROMPT
    print("首轮注入 System Prompt OK")

    print("\n>>> LangGraph 图结构离线自测全部通过。")


if __name__ == "__main__":
    main()
