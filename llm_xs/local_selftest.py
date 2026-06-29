"""本地逻辑自测（完全不调用外部 API）。

用于在没有可用 API Key / 余额时，验证项目核心骨架是否正确：
文档切分、本地向量库检索排序、长期记忆落盘与重启恢复、工具逻辑、工具组装。
"""

from __future__ import annotations


def section(title: str) -> None:
    print("\n" + "=" * 52 + "\n" + title + "\n" + "=" * 52)


def main() -> None:
    from app import config, knowledge

    section("[1] 文档加载 + 切分（不调用 API）")
    chunks = knowledge.load_and_split()
    print(f"知识库切分为 {len(chunks)} 个 chunk")
    print("示例 chunk[5]:", chunks[5].page_content[:40].replace("\n", " "))
    assert len(chunks) > 10

    section("[2] 本地向量库：写入 + 余弦检索排序")
    from app.vector_store import LocalVectorStore

    tmp = config.settings.index_dir / "_selftest_vectors.json"
    store = LocalVectorStore(tmp, dim=3)
    store.recreate()
    store.add(
        [
            {"id": 0, "vector": [1.0, 0.0, 0.0], "text": "苹果", "source": "t", "chunk_id": 0},
            {"id": 1, "vector": [0.0, 1.0, 0.0], "text": "香蕉", "source": "t", "chunk_id": 1},
            {"id": 2, "vector": [0.9, 0.1, 0.0], "text": "红苹果", "source": "t", "chunk_id": 2},
        ]
    )
    res = store.search([1.0, 0.0, 0.0], top_k=2)
    print("查询[1,0,0] 的 top2:", [(r["text"], round(r["score"], 3)) for r in res])
    print("count =", store.count())
    assert res[0]["text"] == "苹果" and res[1]["text"] == "红苹果"
    tmp.unlink(missing_ok=True)

    section("[3] 长期记忆 FileBackedStore：落盘 + 模拟重启恢复")
    from app.long_term_memory import FileBackedStore

    mem = config.settings.memory_dir / "_selftest_store.json"
    mem.unlink(missing_ok=True)
    s1 = FileBackedStore(mem)
    s1.put(("students", "stu1", "profile"), "info", {"name": "小明", "grade": "三年级"})
    s1.put(("students", "stu1", "facts"), "fact-1", {"note": "喜欢恐龙"})
    print("记忆文件已生成:", mem.exists())

    s2 = FileBackedStore(mem)  # 模拟进程重启：新实例从文件恢复
    got = s2.get(("students", "stu1", "profile"), "info")
    print("重启后读取 profile:", got.value if got else None)
    facts = [it.value["note"] for it in s2.search(("students", "stu1", "facts"))]
    print("重启后读取 facts:", facts)
    assert got and got.value["name"] == "小明"
    assert facts == ["喜欢恐龙"]
    mem.unlink(missing_ok=True)

    section("[4] 工具逻辑（不调用 API）")
    from app.tools import calculator, get_today_info

    print("calculator((25+17)*3):", calculator.invoke({"expression": "(25 + 17) * 3"}))
    print("calculator(2 ** 5)   :", calculator.invoke({"expression": "2 ** 5"}))
    print("calculator(非法输入)  :", calculator.invoke({"expression": "__import__('os')"}))
    print("get_today_info       :", get_today_info.invoke({}))

    section("[5] Agent 工具清单 + 联网状态")
    from app.config import settings
    from app.tools import build_tools

    names = [getattr(t, "name", str(t)) for t in build_tools()]
    print("已装配工具:", names)
    print("Tavily Key 是否配置:", bool(settings.tavily_api_key))

    print("\n>>> 本地逻辑自测全部通过（不依赖外部 API）。")


if __name__ == "__main__":
    main()
