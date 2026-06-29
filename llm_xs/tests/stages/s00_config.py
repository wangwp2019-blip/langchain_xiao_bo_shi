"""S0 · 配置与导入（离线）。"""

from __future__ import annotations


def run() -> None:
    from app import __version__
    from app.config import BASE_DIR, TUTORIAL_ROOT, settings

    print(f"版本: {__version__}")
    print(f"项目目录: {BASE_DIR}")
    print(f"教程根目录: {TUTORIAL_ROOT}")
    print(f"向量后端: {settings.vector_backend}")
    print(f"长期记忆: {settings.memory_backend}")
    print(f"短期记忆: {settings.short_term_backend}")
    print(f"API 端口: {settings.api_port}")

    assert settings.knowledge_file.exists(), "知识库文件不存在"
    settings.ensure_dirs()
    assert settings.index_dir.is_dir()
    assert settings.memory_dir.is_dir()

    # 核心模块可导入
    from app import agent, knowledge, models  # noqa: F401
    from app.graph import get_kids_graph, get_study_card_graph  # noqa: F401

    missing = settings.check_llm()
    if missing:
        print("[提示] LLM 配置缺失（S8 需要）:", "、".join(missing))
    else:
        print("LLM 配置: OK")

    print("模块导入与路径检查 OK")
