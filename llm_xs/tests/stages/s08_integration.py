"""S8 · 端到端集成（需 LLM API，可选 Embedding）。"""

from __future__ import annotations


def run() -> None:
    from app import agent, config, knowledge

    missing = config.settings.check_llm()
    if missing:
        raise RuntimeError("缺少 LLM 配置，无法跑 S8：" + "、".join(missing))

    s = config.settings
    print(f"向量后端={s.vector_backend} 记忆={s.memory_backend} 短期={s.short_term_backend}")

    n = knowledge.build_index()
    print(f"建索引: {n} 个片段")

    hits = knowledge.retrieve("太阳系有几大行星")
    assert hits, "检索为空"
    print(f"RAG top score={hits[0]['score']:.3f}")

    uid, tid = "stage8-user", "stage8-thread-1"

    a1 = agent.ask("我叫小测试，三年级，最喜欢恐龙", user_id=uid, thread_id=tid)
    print("自我介绍:", a1[:80].replace("\n", " "))
    assert len(a1) > 5

    a2 = agent.ask("帮我算 (25 + 17) * 3", user_id=uid, thread_id=tid)
    print("计算:", a2[:80].replace("\n", " "))
    assert "126" in a2

    a3 = agent.ask("你还记得我叫什么？", user_id=uid, thread_id="stage8-thread-2")
    print("跨 thread 记忆:", a3[:100].replace("\n", " "))

    tokens = list(agent.stream_answer("鼓励我一句", user_id=uid, thread_id=tid))
    assert tokens, "流式输出为空"
    print("流式片段数:", len(tokens))

    card = agent.generate_study_card("长方形面积怎么算？")
    print("学习卡片 topic:", card.topic)
    assert card.topic and card.answer

    print("端到端 Agent 全链路 OK")
