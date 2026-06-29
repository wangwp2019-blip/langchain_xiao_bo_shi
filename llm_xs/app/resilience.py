"""生产级弹性：软超时、指数退避重试（API / LLM / Agent 共用）。"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

from .config import settings
from .engines.util import TimeoutError_, backoff_delay, run_with_timeout

logger = logging.getLogger(__name__)

T = TypeVar("T")


def invoke_with_retry(
    func: Callable[[], T],
    *,
    max_retries: int | None = None,
    base_delay: float | None = None,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """带指数退避的重试调用（最后一次失败则抛出原异常）。"""
    attempts = max_retries if max_retries is not None else settings.llm_max_retries
    delay_base = base_delay if base_delay is not None else settings.llm_retry_base_delay
    last_exc: BaseException | None = None
    for attempt in range(attempts + 1):
        try:
            return func()
        except retry_on as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            wait = backoff_delay(attempt, delay_base, settings.llm_retry_max_delay)
            logger.warning("调用失败，%ss 后重试 (%d/%d): %s", wait, attempt + 1, attempts, exc)
            time.sleep(wait)
    assert last_exc is not None
    raise last_exc


async def invoke_with_retry_async(
    func: Callable[[], Awaitable[T]],
    *,
    max_retries: int | None = None,
    base_delay: float | None = None,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """异步版指数退避重试。"""
    attempts = max_retries if max_retries is not None else settings.llm_max_retries
    delay_base = base_delay if base_delay is not None else settings.llm_retry_base_delay
    last_exc: BaseException | None = None
    for attempt in range(attempts + 1):
        try:
            return await func()
        except retry_on as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            wait = backoff_delay(attempt, delay_base, settings.llm_retry_max_delay)
            logger.warning("异步调用失败，%ss 后重试 (%d/%d): %s", wait, attempt + 1, attempts, exc)
            await asyncio.sleep(wait)
    assert last_exc is not None
    raise last_exc


def ask_with_timeout(
    question: str,
    user_id: str,
    thread_id: str,
    *,
    timeout: float | None = None,
) -> str:
    """Agent 问答：软超时 + 重试（同步路径，CLI/Worker 用）。"""
    from .agent import ask

    limit = timeout if timeout is not None else settings.chat_timeout_seconds

    def _call() -> str:
        return invoke_with_retry(
            lambda: ask(question, user_id=user_id, thread_id=thread_id),
            retry_on=(TimeoutError_, ConnectionError, OSError),
        )

    return run_with_timeout(_call, limit)


async def ask_with_timeout_async(
    question: str,
    user_id: str,
    thread_id: str,
    *,
    timeout: float | None = None,
) -> str:
    """Agent 问答：asyncio 硬超时 + 异步重试（API 主路径）。"""
    from .agent import ask_async

    limit = timeout if timeout is not None else settings.chat_timeout_seconds

    async def _call() -> str:
        return await invoke_with_retry_async(
            lambda: ask_async(question, user_id=user_id, thread_id=thread_id),
            retry_on=(TimeoutError_, ConnectionError, OSError, asyncio.TimeoutError),
        )

    return await asyncio.wait_for(_call(), timeout=limit)


async def stream_ask_async(
    question: str,
    user_id: str,
    thread_id: str,
) -> AsyncIterator[str]:
    """Agent 流式问答：逐 token/chunk 产出（API SSE 主路径）。"""
    from .agent import stream_answer_async

    async for chunk in stream_answer_async(
        question, user_id=user_id, thread_id=thread_id
    ):
        if chunk:
            yield chunk
