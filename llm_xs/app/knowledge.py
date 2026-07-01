"""RAG 知识库：文档加载、切分、建索引、检索、上下文格式化。

生产路径（默认）：LlamaIndex ``VectorStoreIndex`` + Retriever（``app.rag``）。
降级路径：``keyword`` 关键词检索（无 Embedding）；``legacy`` 自研 JSON 向量库。
"""

from __future__ import annotations

from typing import Any

from .config import settings


def apply_retrieval_scope(
    grade: int | None,
    subject: str | None,
) -> tuple[int | None, str | None]:
    """年级/学科过滤开关：默认关闭，全库按相似度检索。"""
    if not settings.knowledge_scope_filter:
        return None, None
    return grade, subject


def _use_llamaindex() -> bool:
    from .rag.llamaindex_rag import is_active

    return is_active()


def _legacy_build_index() -> int:
    from langchain_community.document_loaders import TextLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    from .models import get_embeddings
    from .vector_store import get_vector_store, needs_embedding

    if not settings.knowledge_file.exists():
        raise FileNotFoundError(f"找不到知识库文件：{settings.knowledge_file}")

    loader = TextLoader(file_path=str(settings.knowledge_file), encoding="utf-8")
    documents = loader.load()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n==============================\n", "\n\n", "\n", "。", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    texts = [c.page_content for c in chunks if len(c.page_content.strip()) >= 10]

    store = get_vector_store()
    store.recreate()
    if needs_embedding():
        vectors = get_embeddings().embed_documents(texts)
        items = [
            {
                "id": i,
                "vector": vectors[i],
                "text": texts[i],
                "source": settings.knowledge_file.name,
                "chunk_id": i,
            }
            for i in range(len(texts))
        ]
    else:
        items = [
            {"id": i, "text": texts[i], "source": settings.knowledge_file.name, "chunk_id": i}
            for i in range(len(texts))
        ]
    store.add(items)
    return len(items)


def build_index() -> int:
    """重建知识库索引，返回写入的 chunk 数量。"""
    if _use_llamaindex():
        from .rag.llamaindex_rag import build_index as li_build

        return li_build()
    return _legacy_build_index()


def get_index_count() -> int:
    """当前索引片段数（health / ready 探针用）。"""
    if _use_llamaindex():
        from .rag.llamaindex_rag import index_count

        return index_count()
    try:
        from .vector_store import get_vector_store

        return get_vector_store().count()
    except Exception:
        return 0


def retrieve(
    query: str,
    top_k: int | None = None,
    *,
    grade: int | None = None,
    subject: str | None = None,
) -> list[dict[str, Any]]:
    """在知识库中检索与 query 最相关的若干片段。"""
    k = top_k or settings.retrieve_top_k
    grade, subject = apply_retrieval_scope(grade, subject)
    if _use_llamaindex():
        from .rag.llamaindex_rag import retrieve as li_retrieve

        return li_retrieve(query, top_k=k, grade=grade, subject=subject)
    from .vector_store import get_vector_store

    return get_vector_store().search_by_text(query, k)


def format_context(hits: list[dict[str, Any]]) -> str:
    """把检索结果拼接成可读的上下文字符串。"""
    if not hits:
        return "（知识库中没有找到相关内容）"
    blocks = []
    for i, hit in enumerate(hits, 1):
        score = hit.get("score", 0.0)
        blocks.append(f"[资料{i} | 相似度 {score:.3f}]\n{hit['text']}")
    return "\n\n".join(blocks)
