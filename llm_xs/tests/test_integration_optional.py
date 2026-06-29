"""S8 · 可选端到端集成（需 LLM API，无 Key 时自动跳过）。"""

from __future__ import annotations

import pytest

import app.config as cfg

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def require_llm():
    missing = cfg.settings.check_llm()
    if missing:
        pytest.skip("缺少 LLM 配置：" + "、".join(missing))


def test_agent_ask_calculator(require_llm):
    from app import agent

    answer = agent.ask("(25 + 17) * 3 等于多少？", user_id="itest", thread_id="itest-1")
    assert "126" in answer


def test_agent_stream(require_llm):
    from app import agent

    tokens = list(agent.stream_answer("鼓励我一句", user_id="itest", thread_id="itest-2"))
    assert tokens
    assert len("".join(tokens)) > 3


def test_generate_study_card_online(require_llm):
    from app import agent

    card = agent.generate_study_card("长方形面积怎么算？")
    assert card.topic
    assert card.answer


def test_knowledge_retrieve_with_backend(require_llm, keyword_backend):
    from app.knowledge import build_index, retrieve

    n = build_index()
    assert n > 0
    hits = retrieve("太阳系有几大行星")
    assert hits
