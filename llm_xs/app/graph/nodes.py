"""LangGraph 图节点函数。

每个节点是一个 ``(state) -> partial_state`` 的纯函数（或带副作用的 IO 函数），
LangGraph 负责把返回值 merge 进全局 State。

主对话图节点
------------
- ``call_model``：绑定 tools 的 LLM，决定是否发起 tool_calls（ReAct 的"思考"步）。
- ``tools``：由 ``ToolNode`` 提供（见 ``builder.py``），执行 tool_calls（ReAct 的"行动"步）。

学习卡片子图节点
----------------
- ``retrieve_context``：RAG 检索，把资料写入 ``state["context"]``。
- ``generate_card_json``：LLM 根据 question + context 生成 JSON 文本。
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from ..knowledge import format_context, retrieve
from ..models import get_llm
from ..resilience import invoke_with_retry
from ..tools import build_tools
from .prompts import (
    STUDY_CARD_SYSTEM_PROMPT,
    build_kids_system_prompt,
    build_study_card_user_prompt,
    load_prompt_context,
)
from .state import KidsGraphState, StudyCardGraphState


def _ensure_system_message(
    messages: list[BaseMessage],
    user_id: str | None = None,
) -> list[BaseMessage]:
    """首轮对话注入 System Prompt（checkpoint 持久化后不再重复注入）。"""
    if messages and isinstance(messages[0], SystemMessage):
        return messages
    ctx = load_prompt_context(user_id)
    return [SystemMessage(content=build_kids_system_prompt(ctx)), *messages]


def call_model(state: KidsGraphState) -> dict:
    """Agent 节点：调用 LLM，可能返回带 tool_calls 的 AIMessage。"""
    tools = build_tools()
    llm = get_llm().bind_tools(tools)
    messages = _ensure_system_message(list(state["messages"]), state.get("user_id"))
    response = invoke_with_retry(lambda: llm.invoke(messages))
    return {"messages": [response]}


def retrieve_context(state: StudyCardGraphState) -> dict:
    """学习卡片图：RAG 检索节点。"""
    hits = retrieve(state["question"])
    return {"context": format_context(hits)}


def generate_card_json(state: StudyCardGraphState) -> dict:
    """学习卡片图：LLM 生成 JSON 节点。"""
    question = state["question"]
    context = state.get("context") or "（知识库中没有找到相关内容）"
    user_prompt = build_study_card_user_prompt(question, context)
    response = invoke_with_retry(
        lambda: get_llm().invoke(
            [
                SystemMessage(content=STUDY_CARD_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
        )
    )
    text = response.content if isinstance(response, AIMessage) else str(response)
    return {"card_json": text}
