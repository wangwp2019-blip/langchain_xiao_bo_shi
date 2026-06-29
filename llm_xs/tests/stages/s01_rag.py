"""S1 · RAG 基础设施（离线，不调 Embedding API）。"""

from __future__ import annotations


def run() -> None:
    from app import config, knowledge
    from app.vector_store import KeywordStore, LocalVectorStore, _tokenize

    chunks = knowledge.load_and_split()
    print(f"知识库切分: {len(chunks)} 个 chunk")
    assert len(chunks) > 10, "chunk 数量过少"
    sample = chunks[5].page_content[:50].replace("\n", " ")
    print(f"示例 chunk[5]: {sample}…")

    # 本地向量库（模拟向量，不调 API）
    tmp = config.settings.index_dir / "_stage1_vectors.json"
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
    print("向量检索 top2:", [(r["text"], round(r["score"], 3)) for r in res])
    assert res[0]["text"] == "苹果" and res[1]["text"] == "红苹果"
    tmp.unlink(missing_ok=True)

    # 关键词检索（不调 API）
    kw_tmp = config.settings.index_dir / "_stage1_keyword.json"
    kw = KeywordStore(kw_tmp)
    kw.recreate()
    kw.add(
        [
            {"id": 0, "text": "太阳系有八大行星", "source": "t", "chunk_id": 0},
            {"id": 1, "text": "过马路要走斑马线", "source": "t", "chunk_id": 1},
        ]
    )
    hits = kw.search_by_text("太阳系 行星", top_k=1)
    print("关键词检索:", hits[0]["text"], f"score={hits[0]['score']:.3f}")
    assert hits and "行星" in hits[0]["text"]
    kw_tmp.unlink(missing_ok=True)

    # 分词器
    tokens = _tokenize("太阳系有几大行星")
    assert "太阳" in tokens or "行星" in tokens
    print("中文 bigram 分词 OK")
