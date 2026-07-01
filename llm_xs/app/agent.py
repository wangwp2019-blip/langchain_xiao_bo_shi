"""对外问答接口（LangGraph 原生版）。

底层不再使用 ``create_agent`` 黑盒，而是调用显式编译的 ``StateGraph``：
- 主对话：``get_kids_graph()``（ReAct：call_model ↔ tools）
- 学习卡片：``get_study_card_graph()``（retrieve → generate）

上层 API（``ask`` / ``stream_answer`` / ``generate_study_card``）签名与旧项目保持一致，
便于 ``api.py``、``cli.py``、``engines/*`` 无缝复用。
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Iterator

from langchain_core.messages import AIMessageChunk, HumanMessage, ToolMessage

from .graph import get_kids_graph, get_study_card_graph
from .schemas import StudyCard
from .tools import bind_rag_student, unbind_rag_student


def _graph_config(thread_id: str, user_id: str = "default-student") -> dict:
    return {"configurable": {"thread_id": thread_id, "user_id": user_id}}


def ask(
    question: str,
    user_id: str = "default-student",
    thread_id: str = "default-thread",
) -> str:
    """一次性问答，返回完整答案文本。"""
    graph = get_kids_graph()
    token = bind_rag_student(user_id)
    try:
        result = graph.invoke(
            {"messages": [HumanMessage(content=question)], "user_id": user_id},
            config=_graph_config(thread_id, user_id),
        )
    finally:
        unbind_rag_student(token)
    return result["messages"][-1].content


async def ask_async(
    question: str,
    user_id: str = "default-student",
    thread_id: str = "default-thread",
) -> str:
    """异步一次性问答（API 主路径，graph.ainvoke 不阻塞 worker 线程）。"""
    graph = get_kids_graph()
    token = bind_rag_student(user_id)
    try:
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=question)], "user_id": user_id},
            config=_graph_config(thread_id, user_id),
        )
    finally:
        unbind_rag_student(token)
    return result["messages"][-1].content


def stream_answer(
    question: str,
    user_id: str = "default-student",
    thread_id: str = "default-thread",
) -> Iterator[str]:
    """流式问答，逐步产出 AI 回答的文本增量。"""
    graph = get_kids_graph()
    token = bind_rag_student(user_id)
    try:
        for chunk in graph.stream(
            {"messages": [HumanMessage(content=question)], "user_id": user_id},
            config=_graph_config(thread_id, user_id),
            stream_mode="messages",
        ):
            message = chunk[0]
            if isinstance(message, ToolMessage):
                continue
            content = getattr(message, "content", "")
            if content and isinstance(message, AIMessageChunk):
                yield content
    finally:
        unbind_rag_student(token)


async def stream_answer_async(
    question: str,
    user_id: str = "default-student",
    thread_id: str = "default-thread",
) -> AsyncIterator[str]:
    """异步流式问答。"""
    graph = get_kids_graph()
    token = bind_rag_student(user_id)
    try:
        async for chunk in graph.astream(
            {"messages": [HumanMessage(content=question)], "user_id": user_id},
            config=_graph_config(thread_id, user_id),
            stream_mode="messages",
        ):
            message = chunk[0]
            if isinstance(message, ToolMessage):
                continue
            content = getattr(message, "content", "")
            if content and isinstance(message, AIMessageChunk):
                yield content
    finally:
        unbind_rag_student(token)


def generate_study_card(question: str) -> StudyCard:
    """结合知识库资料，把答案整理成结构化的学习卡片（LangGraph 子图）。"""
    graph = get_study_card_graph()
    result = graph.invoke({"question": question})
    text = result.get("card_json") or ""
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            return StudyCard.model_validate_json(json_match.group())
        except Exception:
            pass
    raise ValueError(f"无法从模型输出中解析学习卡片：{text[:200]}")


async def generate_study_card_async(question: str) -> StudyCard:
    """异步生成学习卡片。"""
    graph = get_study_card_graph()
    result = await graph.ainvoke({"question": question})
    text = result.get("card_json") or ""
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            return StudyCard.model_validate_json(json_match.group())
        except Exception:
            pass
    raise ValueError(f"无法从模型输出中解析学习卡片：{text[:200]}")
