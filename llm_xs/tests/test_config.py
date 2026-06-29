"""S0 · 配置、路径与模块导入。"""

from __future__ import annotations

import app.config as cfg


def test_version_and_paths():
    from app import __version__
    from app.config import BASE_DIR, TUTORIAL_ROOT, settings

    assert __version__
    assert BASE_DIR.is_dir()
    assert TUTORIAL_ROOT.is_dir()
    assert settings.knowledge_file.exists()


def test_ensure_dirs():
    settings = cfg.settings
    settings.ensure_dirs()
    assert settings.index_dir.is_dir()
    assert settings.memory_dir.is_dir()


def test_rag_engine_mapping():
    cfg.settings.vector_backend = "keyword"
    assert cfg.settings.rag_engine == "keyword"
    cfg.settings.vector_backend = "local"
    assert cfg.settings.rag_engine == "llamaindex"
    cfg.settings.vector_backend = "milvus"
    assert cfg.settings.rag_engine == "llamaindex"


def test_core_imports():
    from app import agent, knowledge, models  # noqa: F401
    from app.graph import get_kids_graph, get_study_card_graph  # noqa: F401

    assert get_kids_graph is not None
    assert get_study_card_graph is not None


def test_check_llm_returns_list():
    missing = cfg.settings.check_llm()
    assert isinstance(missing, list)
