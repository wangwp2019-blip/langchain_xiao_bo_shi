"""LlamaIndex 嵌入适配：复用 LangChain init_embeddings（BGE-M3 / 硅基流动等）。"""

from __future__ import annotations

from typing import Any

from llama_index.core.base.embeddings.base import BaseEmbedding, Embedding
from llama_index.core.bridge.pydantic import PrivateAttr

from ..config import settings


class LangchainEmbeddingAdapter(BaseEmbedding):
    """将已配置好的 LangChain Embeddings 接入 LlamaIndex VectorStoreIndex。"""

    _embeddings: Any = PrivateAttr()

    def __init__(self, **kwargs: Any) -> None:
        from ..models import get_embeddings

        super().__init__(model_name=settings.embed_model, **kwargs)
        self._embeddings = get_embeddings()

    @classmethod
    def class_name(cls) -> str:
        return "LangchainEmbeddingAdapter"

    def _get_query_embedding(self, query: str) -> Embedding:
        return self._embeddings.embed_query(query)

    def _get_text_embedding(self, text: str) -> Embedding:
        return self._embeddings.embed_documents([text])[0]

    def _get_text_embeddings(self, texts: list[str]) -> list[Embedding]:
        return self._embeddings.embed_documents(texts)

    async def _aget_query_embedding(self, query: str) -> Embedding:
        if hasattr(self._embeddings, "aembed_query"):
            return await self._embeddings.aembed_query(query)
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> Embedding:
        if hasattr(self._embeddings, "aembed_documents"):
            vecs = await self._embeddings.aembed_documents([text])
            return vecs[0]
        return self._get_text_embedding(text)
