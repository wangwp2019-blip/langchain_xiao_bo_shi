"""离线灌库入口（LlamaIndex 生产级 RAG）。

用法：
    python run_ingest.py              # 源文件变更或索引为空时灌库
    python run_ingest.py --force      # 强制全量重建（Milvus overwrite）
    python run_ingest.py --verify "太阳系有几大行星"
    python run_ingest.py --status     # 仅查看 manifest / 索引状态
"""

from __future__ import annotations

import argparse
import json
import sys

from app.config import settings
from app.knowledge import build_index, get_index_count


def main() -> int:
    parser = argparse.ArgumentParser(description="小博士知识库离线灌库（LlamaIndex）")
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制全量重建（Milvus 会 overwrite 集合）",
    )
    parser.add_argument(
        "--verify",
        metavar="QUERY",
        default=None,
        help="灌库后执行检索验证并打印 Top-K 结果",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="仅输出索引/manifest 状态，不灌库",
    )
    args = parser.parse_args()

    print(f"知识库文件 ：{settings.knowledge_file}")
    print(f"向量库后端 ：{settings.vector_backend}（RAG 引擎：{settings.rag_engine}）")
    print(f"嵌入模型   ：{settings.embed_model}（{settings.embed_dim} 维）")

    if settings.rag_engine == "llamaindex":
        from app.rag.llamaindex_rag import (
            _manifest_path,
            _read_manifest,
            check_rag_ready,
        )

        if args.status:
            ready = check_rag_ready()
            manifest = _read_manifest()
            print("\n--- RAG 状态 ---")
            print(json.dumps(ready, ensure_ascii=False, indent=2))
            if manifest:
                print(f"\nmanifest: {_manifest_path()}")
                print(json.dumps(manifest, ensure_ascii=False, indent=2))
            return 0

        if not settings.embedding_configured:
            print("\n[错误] 未配置 Embedding API，无法灌库。", file=sys.stderr)
            print("请设置 SILICONFLOW_API_KEY / KIDS_EMBED_API_KEY 等。", file=sys.stderr)
            return 1

        print("\n开始灌库（加载 -> 切分 -> Embedding -> VectorStoreIndex）...")
        from app.rag.llamaindex_rag import build_index as li_build

        count = li_build(force=args.force)
    else:
        print("\n开始灌库（keyword/legacy 后端）...")
        count = build_index()

    print(f"\n完成！写入/更新 {count} 个知识片段。")
    print(f"当前索引片段数：{get_index_count()}")

    if args.verify and settings.rag_engine == "llamaindex":
        from app.rag.llamaindex_rag import verify_retrieval

        hits = verify_retrieval(args.verify, top_k=3)
        print(f"\n--- 检索验证：「{args.verify}」---")
        if not hits:
            print("（无命中，请检查索引或 Embedding 配置）")
            return 2
        for i, h in enumerate(hits, 1):
            preview = (h.get("text") or "")[:120].replace("\n", " ")
            print(f"  [{i}] score={h.get('score', 0):.3f} | {preview}...")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
