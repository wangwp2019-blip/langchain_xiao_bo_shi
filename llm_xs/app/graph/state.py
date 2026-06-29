"""LangGraph 显式 State 定义。

旧项目用 ``create_agent`` + ``AgentState`` 黑盒封装 State；
本项目用 ``TypedDict`` + ``add_messages`` **手写 State**，便于：

1. 在 LangGraph Studio / 调试器里看清每个字段；
2. 在节点函数里按需扩展字段（如 ``retrieved_context``）；
3. 与 LangGraph 官方教程的 ``StateGraph`` 写法一致。

字段说明
--------
- ``messages``：对话消息列表，``add_messages``  reducer 负责追加/去重（LangGraph 标准写法）。
- ``user_id``：学生身份，长期记忆工具通过 ``ToolRuntime.state`` 读取。
"""

from __future__ import annotations

from typing import Annotated, NotRequired

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class KidsGraphState(TypedDict):
    """主对话图 State。"""

    messages: Annotated[list[BaseMessage], add_messages]
    user_id: NotRequired[str]


class StudyCardGraphState(TypedDict):
    """学习卡片子图 State（RAG 检索 → LLM 生成 → JSON 解析）。"""

    question: str
    context: NotRequired[str]
    card_json: NotRequired[str]
