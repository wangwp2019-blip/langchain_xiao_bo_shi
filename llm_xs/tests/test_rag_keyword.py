"""S1/S5 · keyword 向量库与知识库检索（零 Embedding）。"""

from __future__ import annotations

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

import app.config as cfg
from app.knowledge import build_index, format_context, retrieve
from app.vector_store import KeywordStore, LocalVectorStore, _tokenize, get_vector_store


def test_load_and_split_knowledge():
    loader = TextLoader(file_path=str(cfg.settings.knowledge_file), encoding="utf-8")
    documents = loader.load()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg.settings.chunk_size,
        chunk_overlap=cfg.settings.chunk_overlap,
        separators=["\n==============================\n", "\n\n", "\n", "。", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    assert len(chunks) > 10


def test_local_vector_store_cosine(tmp_path):
    path = tmp_path / "vec.json"
    store = LocalVectorStore(path, dim=3)
    store.recreate()
    store.add(
        [
            {"id": 0, "vector": [1.0, 0.0, 0.0], "text": "苹果", "source": "t", "chunk_id": 0},
            {"id": 1, "vector": [0.0, 1.0, 0.0], "text": "香蕉", "source": "t", "chunk_id": 1},
            {"id": 2, "vector": [0.9, 0.1, 0.0], "text": "红苹果", "source": "t", "chunk_id": 2},
        ]
    )
    hits = store.search([1.0, 0.0, 0.0], top_k=2)
    assert hits[0]["text"] == "苹果"
    assert hits[1]["text"] == "红苹果"
    assert store.count() == 3


def test_keyword_store_search(tmp_path):
    path = tmp_path / "kw.json"
    store = KeywordStore(path)
    store.recreate()
    store.add(
        [
            {"id": 0, "text": "太阳系有八大行星", "source": "t", "chunk_id": 0},
            {"id": 1, "text": "过马路要走斑马线", "source": "t", "chunk_id": 1},
        ]
    )
    hits = store.search_by_text("太阳系 行星", top_k=1)
    assert hits and "行星" in hits[0]["text"]


def test_tokenize_chinese():
    tokens = _tokenize("太阳系有几大行星")
    assert "太阳" in tokens or "行星" in tokens


def test_keyword_build_and_retrieve(keyword_backend):
    n = build_index()
    assert n > 0
    hits = retrieve("太阳系有几大行星")
    assert hits
    assert any("行星" in h["text"] for h in hits)

    ctx = format_context(hits[:2])
    assert "资料" in ctx


def test_format_context_empty():
    assert "没有找到" in format_context([])


def test_retrieve_context_node(keyword_backend):
    from app.graph.nodes import retrieve_context

    build_index()
    out = retrieve_context({"question": "太阳系有几大行星？"})
    assert "context" in out
    assert len(out["context"]) > 20
