"""大模型与嵌入模型的初始化（统一入口，带单例缓存）。

沿用教程的统一写法：
- LLM 用 `init_chat_model`（CloseAI / OpenAI 兼容）。
- Embedding 用 `init_embeddings`（硅基流动 BGE-M3，1024 维）。
"""

from __future__ import annotations

from functools import lru_cache

from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings

from .config import settings


@lru_cache(maxsize=1)
def get_llm():
    """返回对话大模型（单例）。"""
    missing = settings.check_llm()
    if missing:
        raise RuntimeError(
            "缺少对话大模型配置：" + "、".join(missing) + "。请在 .env 中配置后重试。"
        )
    return init_chat_model(
        model=settings.llm_model,
        model_provider=settings.llm_provider,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )


@lru_cache(maxsize=1)
def get_embeddings():
    """返回嵌入模型（单例）。"""
    missing = settings.check_embedding()
    if missing:
        raise RuntimeError(
            "缺少嵌入模型配置：" + "、".join(missing) + "。请在 .env 中配置后重试。"
        )
    return init_embeddings(
        model="openai:" + settings.embed_model,
        api_key=settings.embed_api_key,
        base_url=settings.embed_base_url,
    )


@lru_cache(maxsize=1)
def get_llm_for_structured():
    """返回用于结构化输出（ToolStrategy）的 LLM（单例）。

    推理模型的 thinking mode 不支持 tool_choice，无法配合 ToolStrategy。
    可通过 ``KIDS_STRUCTURED_LLM_MODEL`` 指定一个不带 thinking 的模型
    （如 ``deepseek-chat``），复用主 LLM 的 key / base_url。
    未配置时回退到主 LLM（适用于主 LLM 本身不带 thinking 的情况）。
    """
    if not settings.structured_llm_model:
        return get_llm()
    return init_chat_model(
        model=settings.structured_llm_model,
        model_provider=settings.llm_provider,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )
