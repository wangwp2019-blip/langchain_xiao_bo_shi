"""端到端冒烟测试：验证项目各能力可运行。

运行：python smoke_test.py
会真实调用一次 Embedding 与若干次 LLM（用量很小）。
"""

from __future__ import annotations


def main() -> None:
    print("[1] 导入模块 ...")
    from app import agent, config, knowledge

    s = config.settings
    print(f"    OK  向量后端={s.vector_backend} 长期记忆={s.memory_backend} 短期记忆={s.short_term_backend}")

    print("[2] 建知识库索引 ...")
    n = knowledge.build_index()
    print(f"    OK  写入 {n} 个片段")

    print("[3] RAG 检索：太阳系有几大行星？")
    hits = knowledge.retrieve("太阳系有几大行星")
    assert hits, "检索结果为空"
    for h in hits[:2]:
        print(f"    score={h['score']:.3f}  {h['text'][:28]}...")

    uid, tid = "smoke-user", "smoke-thread-1"

    print("[4] Agent 自我介绍（触发长期记忆保存）")
    a1 = agent.ask("我叫小测试，今年上三年级，最喜欢恐龙", user_id=uid, thread_id=tid)
    print("    小博士:", a1[:80])

    print("[5] Agent 知识库问答（触发 RAG 工具）")
    a2 = agent.ask("太阳系有几大行星？分别是什么？", user_id=uid, thread_id=tid)
    print("    小博士:", a2[:120])

    print("[6] Agent 计算（触发 calculator 工具）")
    a3 = agent.ask("帮我算一下 (25 + 17) * 3", user_id=uid, thread_id=tid)
    print("    小博士:", a3[:80])

    print("[7] 跨会话长期记忆（换新 thread，同一 user）")
    a4 = agent.ask("你还记得我叫什么、上几年级吗？", user_id=uid, thread_id="smoke-thread-2")
    print("    小博士:", a4[:120])

    print("[8] 长期记忆落盘检查")
    f = config.settings.long_term_store_file
    print("    文件存在:", f.exists())
    if f.exists():
        print("    内容:", f.read_text(encoding="utf-8").replace("\n", " ")[:200])

    print("[9] 流式输出测试")
    print("    小博士: ", end="", flush=True)
    for tok in agent.stream_answer("用一句话鼓励我", user_id=uid, thread_id=tid):
        print(tok, end="", flush=True)
    print()

    print("[10] 结构化学习卡片（ToolStrategy）")
    card = agent.generate_study_card("长方形的面积怎么算？")
    print("    topic:", card.topic)
    print("    answer:", card.answer[:60])
    print("    knowledge_points:", card.knowledge_points)
    print("    encouragement:", card.encouragement)

    print("\n>>> 全部冒烟测试完成！")


if __name__ == "__main__":
    main()
