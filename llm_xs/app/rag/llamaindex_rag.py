"""LlamaIndex 生产级 RAG：VectorStoreIndex + Retriever + Milvus / 本地持久化。

架构
----
- ``KIDS_VECTOR_BACKEND=local``（默认）：磁盘持久化索引 ``data/index/llamaindex/``
- ``KIDS_VECTOR_BACKEND=milvus``：``llama-index-vector-stores-milvus``，**集合存在即复用**
- ``KIDS_VECTOR_BACKEND=memory``：进程内索引（仅演示，不持久化）

灌库
----
``python run_ingest.py [--force] [--verify QUERY]``

``--force`` 或 ``KIDS_FORCE_REINGEST=true`` 时全量重建；Milvus 侧 ``overwrite=True`` 替换集合。
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..config import settings

logger = logging.getLogger(__name__)

_SEPARATORS = [
    "\n==============================\n",
    "\n\n",
    "\n",
    "。",
    " ",
    "",
]

_INDEX: Any | None = None
_INDEX_LOCK = threading.Lock()
_MANIFEST = "manifest.json"


def is_active() -> bool:
    return settings.vector_backend.lower() in ("local", "milvus", "memory")


def _persist_dir() -> Path:
    path = settings.index_dir / "llamaindex"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _manifest_path() -> Path:
    return _persist_dir() / _MANIFEST


def _source_fingerprint() -> dict[str, Any]:
    path = settings.knowledge_file
    stat = path.stat()
    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "path": str(path),
        "size": stat.st_size,
        "mtime": stat.st_mtime,
        "sha256": content_hash,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "embed_model": settings.embed_model,
        "embed_dim": settings.embed_dim,
    }


def _read_manifest() -> dict[str, Any] | None:
    mp = _manifest_path()
    if not mp.exists():
        return None
    try:
        return json.loads(mp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_manifest(chunk_count: int) -> None:
    payload = {
        "version": 1,
        "backend": settings.vector_backend.lower(),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "chunk_count": chunk_count,
        "source": _source_fingerprint(),
        "milvus": {
            "uri": settings.milvus_uri,
            "collection": settings.milvus_collection,
        }
        if settings.vector_backend.lower() == "milvus"
        else None,
    }
    _manifest_path().write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _manifest_matches() -> bool:
    old = _read_manifest()
    if not old:
        return False
    if old.get("backend") != settings.vector_backend.lower():
        return False
    return old.get("source") == _source_fingerprint()


def _is_separator_only(text: str) -> bool:
    cleaned = text.replace("=", "").replace("-", "").strip()
    return len(cleaned) < 10


def load_documents() -> list:
    """加载并切分知识库为 LlamaIndex Document 列表。"""
    if not settings.knowledge_file.exists():
        raise FileNotFoundError(f"找不到知识库文件：{settings.knowledge_file}")

    loader = TextLoader(file_path=str(settings.knowledge_file), encoding="utf-8")
    raw = loader.load()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=_SEPARATORS,
    )
    chunks = splitter.split_documents(raw)
    chunks = [c for c in chunks if not _is_separator_only(c.page_content)]

    from llama_index.core import Document

    return [
        Document(
            text=c.page_content,
            metadata={
                "source": settings.knowledge_file.name,
                "chunk_id": i,
                "doc_id": f"{settings.knowledge_file.name}:{i}",
            },
        )
        for i, c in enumerate(chunks)
    ]


def configure_embeddings() -> None:
    """配置 OpenAI 兼容 Embedding（硅基流动 / OpenAI 等）。"""
    from llama_index.core import Settings as LISettings
    from llama_index.embeddings.openai import OpenAIEmbedding

    if not settings.embedding_configured:
        raise RuntimeError(
            "LlamaIndex RAG 需要 Embedding API。"
            "请配置 KIDS_EMBED_* 或 SILICONFLOW_* 环境变量。"
        )
    LISettings.embed_model = OpenAIEmbedding(
        model=settings.embed_model,
        api_key=settings.embed_api_key,
        api_base=settings.embed_base_url,
    )


def _milvus_collection_exists() -> bool:
    try:
        from pymilvus import MilvusClient

        client = MilvusClient(uri=settings.milvus_uri)
        return bool(client.has_collection(settings.milvus_collection))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Milvus 连通性检查失败: %s", exc)
        return False


def _milvus_row_count() -> int:
    try:
        from pymilvus import MilvusClient

        client = MilvusClient(uri=settings.milvus_uri)
        if not client.has_collection(settings.milvus_collection):
            return 0
        stats = client.get_collection_stats(settings.milvus_collection)
        return int(stats.get("row_count", 0))
    except Exception:
        return 0


def _milvus_should_overwrite(*, force: bool, collection_exists: bool) -> bool:
    """Milvus 灌库策略：集合存在且非 force 时不 overwrite。"""
    return force or not collection_exists


def _build_milvus_index(docs: list, *, force: bool) -> Any:
    from llama_index.core import StorageContext, VectorStoreIndex
    from llama_index.vector_stores.milvus import MilvusVectorStore

    exists = _milvus_collection_exists()
    overwrite = _milvus_should_overwrite(force=force, collection_exists=exists)

    if exists and not force:
        logger.info(
            "Milvus 集合 %s 已存在（%d 行），直接复用",
            settings.milvus_collection,
            _milvus_row_count(),
        )
        vector_store = MilvusVectorStore(
            uri=settings.milvus_uri,
            collection_name=settings.milvus_collection,
            dim=settings.embed_dim,
            overwrite=False,
        )
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        return VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            storage_context=storage_context,
        )

    logger.info(
        "Milvus 灌库：%s 集合 %s（%d 片段，overwrite=%s）",
        "重建" if exists else "创建",
        settings.milvus_collection,
        len(docs),
        overwrite,
    )
    vector_store = MilvusVectorStore(
        uri=settings.milvus_uri,
        collection_name=settings.milvus_collection,
        dim=settings.embed_dim,
        overwrite=overwrite,
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return VectorStoreIndex.from_documents(docs, storage_context=storage_context)


def _build_local_index(docs: list, *, force: bool) -> Any:
    from llama_index.core import StorageContext, VectorStoreIndex, load_index_from_storage

    persist = _persist_dir()
    docstore_file = persist / "docstore.json"

    if not force and docstore_file.exists() and _manifest_matches():
        try:
            logger.info("加载本地 LlamaIndex 索引：%s", persist)
            storage_context = StorageContext.from_defaults(persist_dir=str(persist))
            return load_index_from_storage(storage_context)
        except Exception as exc:
            logger.warning("本地索引加载失败，将重建: %s", exc)

    logger.info("本地 LlamaIndex 灌库：%d 片段 -> %s", len(docs), persist)
    index = VectorStoreIndex.from_documents(docs)
    index.storage_context.persist(persist_dir=str(persist))
    return index


def _build_memory_index(docs: list) -> Any:
    from llama_index.core import VectorStoreIndex

    logger.info("内存 LlamaIndex 灌库：%d 片段（进程结束即丢失）", len(docs))
    return VectorStoreIndex.from_documents(docs)


def _load_or_create_index(*, force: bool = False) -> Any:
    configure_embeddings()
    backend = settings.vector_backend.lower()

    need_build = force or not _index_is_populated()
    if not need_build and _manifest_matches():
        return _attach_existing_index(backend)

    docs = load_documents()
    if backend == "milvus":
        index = _build_milvus_index(docs, force=force)
        count = _milvus_row_count() or len(docs)
    elif backend == "memory":
        index = _build_memory_index(docs)
        count = len(docs)
    else:
        index = _build_local_index(docs, force=force)
        count = len(index.docstore.docs)

    _write_manifest(count)
    return index


def _index_is_populated() -> bool:
    backend = settings.vector_backend.lower()
    if backend == "milvus":
        return _milvus_row_count() > 0
    if backend == "memory":
        return _INDEX is not None
    return (_persist_dir() / "docstore.json").exists()


def _attach_existing_index(backend: str) -> Any:
    if backend == "milvus":
        from llama_index.core import StorageContext, VectorStoreIndex
        from llama_index.vector_stores.milvus import MilvusVectorStore

        vector_store = MilvusVectorStore(
            uri=settings.milvus_uri,
            collection_name=settings.milvus_collection,
            dim=settings.embed_dim,
            overwrite=False,
        )
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        return VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            storage_context=storage_context,
        )

    from llama_index.core import StorageContext, load_index_from_storage

    storage_context = StorageContext.from_defaults(persist_dir=str(_persist_dir()))
    return load_index_from_storage(storage_context)


def _get_index_locked():
    global _INDEX
    with _INDEX_LOCK:
        if _INDEX is None:
            _INDEX = _load_or_create_index(force=False)
        return _INDEX


@lru_cache(maxsize=1)
def _get_index():
    return _get_index_locked()


def clear_index_cache() -> None:
    global _INDEX
    with _INDEX_LOCK:
        _INDEX = None
    _get_index.cache_clear()


def build_index(*, force: bool = False) -> int:
    """离线灌库。默认：源文件未变且索引存在则跳过；``force=True`` 全量重建。"""
    env_force = (settings.force_reingest or "").lower() in ("1", "true", "yes")
    do_force = force or env_force

    if not do_force and _manifest_matches() and _index_is_populated():
        logger.info("知识库索引已是最新（manifest 匹配），跳过灌库")
        return index_count()

    global _INDEX
    with _INDEX_LOCK:
        _INDEX = None
    _get_index.cache_clear()

    idx = _load_or_create_index(force=True)
    with _INDEX_LOCK:
        _INDEX = idx
    return index_count()


def index_count() -> int:
    backend = settings.vector_backend.lower()
    if backend == "milvus":
        return _milvus_row_count()
    if backend == "memory":
        try:
            return len(_get_index().docstore.docs)
        except Exception:
            return 0
    manifest = _read_manifest()
    if manifest and "chunk_count" in manifest:
        return int(manifest["chunk_count"])
    try:
        if (_persist_dir() / "docstore.json").exists():
            configure_embeddings()
            from llama_index.core import StorageContext, load_index_from_storage

            ctx = StorageContext.from_defaults(persist_dir=str(_persist_dir()))
            idx = load_index_from_storage(ctx)
            return len(idx.docstore.docs)
    except Exception:
        pass
    return 0


def check_rag_ready() -> dict[str, Any]:
    """就绪探针：Embedding 配置、索引是否可用、manifest 状态。"""
    backend = settings.vector_backend.lower()
    result: dict[str, Any] = {
        "backend": backend,
        "embedding_configured": settings.embedding_configured,
        "index_count": index_count(),
        "manifest_ok": _manifest_matches(),
        "ready": False,
    }
    if not settings.embedding_configured:
        result["error"] = "embedding_not_configured"
        return result
    if backend == "milvus":
        result["milvus_uri"] = settings.milvus_uri
        result["collection"] = settings.milvus_collection
        result["collection_exists"] = _milvus_collection_exists()
        result["ready"] = result["collection_exists"] and result["index_count"] > 0
    else:
        result["ready"] = result["index_count"] > 0
    return result


def retrieve(query: str, top_k: int | None = None) -> list[dict[str, Any]]:
    """VectorStoreIndex Retriever 检索，返回统一 hit 结构。"""
    if not query.strip():
        return []
    k = top_k or settings.retrieve_top_k
    try:
        index = _get_index()
        retriever = index.as_retriever(similarity_top_k=k)
        nodes = retriever.retrieve(query)
    except Exception as exc:
        logger.warning("LlamaIndex 检索失败: %s", exc)
        return []

    hits: list[dict[str, Any]] = []
    for node in nodes:
        hits.append(
            {
                "text": node.get_content(),
                "score": float(node.score or 0.0),
                "source": (node.metadata or {}).get("source", ""),
                "chunk_id": (node.metadata or {}).get("chunk_id"),
            }
        )
    return hits


def verify_retrieval(query: str = "太阳系", top_k: int = 2) -> list[dict[str, Any]]:
    """灌库后验证检索（run_ingest --verify 用）。"""
    return retrieve(query, top_k=top_k)
