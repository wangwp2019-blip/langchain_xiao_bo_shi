"""检索后端抽象层。

提供三种实现，通过配置 ``KIDS_VECTOR_BACKEND`` 切换：

- ``local``（默认）：纯 Python + JSON 文件 + 余弦相似度，需要 Embedding。
- ``milvus``：沿用教程写法，通过 ``pymilvus.MilvusClient`` 连接 Milvus，需要 Embedding。
- ``keyword``：中文 bigram + Jaccard 相似度的关键词检索，**不需要 Embedding**。
  适合没有可用 embedding API 时的降级方案，效果弱于向量检索但零外部依赖。

统一接口：``recreate`` / ``add`` / ``search`` / ``search_by_text`` / ``count``。
``search_by_text`` 是推荐的检索入口：向量后端内部自动 embed 再 search，
keyword 后端直接做文本匹配。返回统一格式 ``[{"text", "score", "chunk_id", "source"}, ...]``。
"""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import settings


class BaseVectorStore:
    """检索后端统一接口。"""

    def recreate(self) -> None:
        raise NotImplementedError

    def add(self, items: list[dict[str, Any]]) -> int:
        """写入数据。向量后端需含 vector 字段；keyword 后端忽略 vector。"""
        raise NotImplementedError

    def search(self, query_vector: list[float], top_k: int) -> list[dict[str, Any]]:
        """向量检索（向量后端使用）。"""
        raise NotImplementedError

    def search_by_text(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """文本检索入口（推荐）。向量后端默认实现：embed 后调用 search。"""
        from .models import get_embeddings

        query_vector = get_embeddings().embed_query(str(query))
        return self.search(query_vector, top_k)

    def count(self) -> int:
        raise NotImplementedError


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


class LocalVectorStore(BaseVectorStore):
    """纯 Python + JSON 文件的本地向量库（默认后端）。"""

    def __init__(self, index_file: Path, dim: int):
        self.index_file = Path(index_file)
        self.dim = dim
        self._items: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self.index_file.exists():
            try:
                payload = json.loads(self.index_file.read_text(encoding="utf-8"))
                self.dim = payload.get("dim", self.dim)
                self._items = payload.get("items", [])
            except (json.JSONDecodeError, OSError):
                self._items = []

    def _save(self) -> None:
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {"dim": self.dim, "items": self._items}
        self.index_file.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def recreate(self) -> None:
        self._items = []
        self._save()

    def add(self, items: list[dict[str, Any]]) -> int:
        self._items.extend(items)
        self._save()
        return len(items)

    def search(self, query_vector: list[float], top_k: int) -> list[dict[str, Any]]:
        scored = []
        for item in self._items:
            score = _cosine_similarity(query_vector, item["vector"])
            scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        results = []
        for score, item in scored[:top_k]:
            results.append(
                {
                    "text": item.get("text", ""),
                    "score": float(score),
                    "chunk_id": item.get("chunk_id"),
                    "source": item.get("source", "unknown"),
                }
            )
        return results

    def count(self) -> int:
        return len(self._items)


class MilvusVectorStore(BaseVectorStore):
    """基于 pymilvus 的向量库（可选后端，沿用教程写法）。"""

    def __init__(self, uri: str, db_name: str, collection: str, dim: int):
        try:
            from pymilvus import MilvusClient
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "使用 Milvus 后端需要先安装 pymilvus：pip install pymilvus，"
                "并启动 Milvus 服务（如 Docker）。"
            ) from exc

        self.collection = collection
        self.dim = dim
        self._client = MilvusClient(uri)

        existed = self._client.list_databases()
        if db_name not in existed:
            self._client.create_database(db_name=db_name)
        self._client.use_database(db_name=db_name)

    def recreate(self) -> None:
        if self._client.has_collection(collection_name=self.collection):
            self._client.drop_collection(collection_name=self.collection)
        self._client.create_collection(
            collection_name=self.collection,
            dimension=self.dim,
            metric_type="COSINE",
        )

    def add(self, items: list[dict[str, Any]]) -> int:
        self._client.upsert(collection_name=self.collection, data=items)
        self._client.flush(collection_name=self.collection)
        return len(items)

    def search(self, query_vector: list[float], top_k: int) -> list[dict[str, Any]]:
        raw = self._client.search(
            collection_name=self.collection,
            data=[query_vector],
            limit=top_k,
            output_fields=["text", "chunk_id", "source"],
        )
        results = []
        for hit in raw[0]:
            entity = hit.get("entity", {})
            results.append(
                {
                    "text": entity.get("text", ""),
                    "score": float(hit.get("distance", 0.0)),
                    "chunk_id": entity.get("chunk_id"),
                    "source": entity.get("source", "unknown"),
                }
            )
        return results

    def count(self) -> int:
        rows = self._client.query(
            collection_name=self.collection,
            filter="id >= 0",
            output_fields=["id"],
        )
        return len(rows)


# ==================== 关键词检索后端（无需 Embedding）====================

_WORD_RE = re.compile(r"[a-zA-Z0-9]+")
_CN_RE = re.compile(r"[\u4e00-\u9fff]")
_STOPWORDS = {"的", "了", "是", "在", "和", "与", "也", "都", "又", "就", "你", "我", "他", "她", "它", "们", "这", "那", "有", "为", "以", "及"}


def _tokenize(text: str) -> set[str]:
    """中文 bigram + 英文/数字单词 的简易分词，不依赖 jieba。"""
    tokens: set[str] = set()
    for m in _WORD_RE.findall(text.lower()):
        if len(m) > 1:
            tokens.add(m)
    chinese = "".join(_CN_RE.findall(text))
    for i in range(len(chinese) - 1):
        bg = chinese[i : i + 2]
        if bg not in _STOPWORDS:
            tokens.add(bg)
    return tokens


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _query_coverage(query_tokens: set[str], doc_tokens: set[str]) -> float:
    """查询覆盖率：doc 命中了 query 中多少关键词。

    比 Jaccard 更适合关键词检索：不会因为 doc 本身 token 少而虚高得分，
    也不会因为 doc 很长而稀释得分。
    """
    if not query_tokens or not doc_tokens:
        return 0.0
    return len(query_tokens & doc_tokens) / len(query_tokens)


class KeywordStore(BaseVectorStore):
    """关键词检索后端（Jaccard 相似度），不需要 Embedding。

    用于没有可用 embedding API 时的降级方案。``add`` 时忽略 vector 字段，
    ``search_by_text`` 直接做关键词匹配，``search`` 不使用。
    """

    def __init__(self, index_file: Path):
        self.index_file = Path(index_file)
        self._items: list[dict[str, Any]] = []
        self._tokens: list[set[str]] = []
        self._load()

    def _load(self) -> None:
        if self.index_file.exists():
            try:
                payload = json.loads(self.index_file.read_text(encoding="utf-8"))
                self._items = payload.get("items", [])
                self._tokens = [set(t) for t in payload.get("tokens", [])]
            except (json.JSONDecodeError, OSError):
                self._items = []
                self._tokens = []

    def _save(self) -> None:
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "items": self._items,
            "tokens": [sorted(t) for t in self._tokens],
        }
        self.index_file.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def recreate(self) -> None:
        self._items = []
        self._tokens = []
        self._save()

    def add(self, items: list[dict[str, Any]]) -> int:
        for item in items:
            self._items.append(item)
            self._tokens.append(_tokenize(item.get("text", "")))
        self._save()
        return len(items)

    def search_by_text(self, query: str, top_k: int) -> list[dict[str, Any]]:
        q_tokens = _tokenize(str(query))
        scored = []
        for item, tok in zip(self._items, self._tokens):
            scored.append((_query_coverage(q_tokens, tok), item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        results = []
        for score, item in scored[:top_k]:
            results.append(
                {
                    "text": item.get("text", ""),
                    "score": float(score),
                    "chunk_id": item.get("chunk_id"),
                    "source": item.get("source", "unknown"),
                }
            )
        return results

    def count(self) -> int:
        return len(self._items)


@lru_cache(maxsize=1)
def get_vector_store() -> BaseVectorStore:
    """根据配置返回检索后端实例（单例）。"""
    settings.ensure_dirs()
    backend = settings.vector_backend.lower()
    if backend == "milvus":
        return MilvusVectorStore(
            uri=settings.milvus_uri,
            db_name=settings.milvus_db,
            collection=settings.milvus_collection,
            dim=settings.embed_dim,
        )
    if backend == "keyword":
        return KeywordStore(index_file=settings.local_index_file)
    return LocalVectorStore(
        index_file=settings.local_index_file,
        dim=settings.embed_dim,
    )


def needs_embedding() -> bool:
    """当前后端是否需要 Embedding（keyword 后端不需要）。"""
    return settings.vector_backend.lower() != "keyword"
