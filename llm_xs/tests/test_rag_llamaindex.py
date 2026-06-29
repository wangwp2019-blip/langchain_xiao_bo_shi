"""LlamaIndex RAG 单元测试（不依赖真实 Milvus / Embedding 网络）。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

import app.config as cfg
from app.rag import llamaindex_rag as rag


def test_is_active_local_backend():
    cfg.settings.vector_backend = "local"
    assert rag.is_active() is True


def test_manifest_fingerprint_stable(tmp_path, monkeypatch):
    kb = tmp_path / "kids_knowledge.txt"
    kb.write_text("地球是太阳系第三颗行星。\n" * 3, encoding="utf-8")
    cfg.settings.knowledge_file = kb
    cfg.settings.index_dir = tmp_path / "index"
    rag.clear_index_cache()

    fp1 = rag._source_fingerprint()
    fp2 = rag._source_fingerprint()
    assert fp1 == fp2
    assert fp1["sha256"]


def test_build_index_skips_when_manifest_matches(tmp_path, monkeypatch):
    kb = tmp_path / "kids_knowledge.txt"
    kb.write_text("测试知识库内容。\n" * 5, encoding="utf-8")
    cfg.settings.knowledge_file = kb
    cfg.settings.index_dir = tmp_path / "index"
    cfg.settings.vector_backend = "memory"
    cfg.settings.embed_model = "test-embed"
    cfg.settings.embed_api_key = "sk-test"
    cfg.settings.embed_base_url = "https://example.com/v1"
    rag.clear_index_cache()

    mock_index = MagicMock()
    mock_index.docstore.docs = {"a": 1, "b": 2}

    with (
        patch.object(rag, "configure_embeddings"),
        patch.object(rag, "load_documents", return_value=[MagicMock()]),
        patch.object(rag, "_build_memory_index", return_value=mock_index),
        patch.object(rag, "_index_is_populated", return_value=True),
        patch.object(rag, "_manifest_matches", return_value=True),
        patch.object(rag, "index_count", return_value=2),
    ):
        count = rag.build_index(force=False)

    assert count == 2


def test_milvus_overwrite_policy():
    assert rag._milvus_should_overwrite(force=False, collection_exists=True) is False
    assert rag._milvus_should_overwrite(force=True, collection_exists=True) is True
    assert rag._milvus_should_overwrite(force=False, collection_exists=False) is True


def test_retrieve_empty_query():
    assert rag.retrieve("  ") == []


def test_is_active_keyword_false():
    cfg.settings.vector_backend = "keyword"
    assert rag.is_active() is False


def test_check_rag_ready_without_embedding(monkeypatch):
    cfg.settings.vector_backend = "local"
    monkeypatch.setattr(cfg.settings, "embed_api_key", None)
    monkeypatch.setattr(cfg.settings, "embed_base_url", None)
    rag.clear_index_cache()
    ready = rag.check_rag_ready()
    assert ready["embedding_configured"] is False
    assert ready["ready"] is False
    assert ready.get("error") == "embedding_not_configured"


def test_load_documents(tmp_path):
    pytest.importorskip("llama_index")
    kb = tmp_path / "kb.txt"
    kb.write_text("地球是太阳系第三颗行星。\n" * 5, encoding="utf-8")
    cfg.settings.knowledge_file = kb
    docs = rag.load_documents()
    assert len(docs) >= 1
    assert "地球" in docs[0].text


def test_manifest_matches_false_when_missing(tmp_path):
    cfg.settings.index_dir = tmp_path / "index"
    rag.clear_index_cache()
    assert rag._manifest_matches() is False

