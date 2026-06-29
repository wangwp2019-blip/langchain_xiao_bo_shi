#!/usr/bin/env python3
"""Milvus 集合元数据导出（配合 volume 备份，便于灾备核对与重建）。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def export_metadata(out_path: Path) -> dict:
    from app.config import settings

    result: dict = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "vector_backend": settings.vector_backend,
        "milvus_uri": settings.milvus_uri,
        "milvus_db": settings.milvus_db,
        "milvus_collection": settings.milvus_collection,
        "collections": [],
        "error": None,
    }

    if settings.vector_backend.lower() != "milvus":
        result["skipped"] = True
        result["reason"] = f"vector_backend={settings.vector_backend} 非 milvus"
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    try:
        from pymilvus import MilvusClient

        client = MilvusClient(uri=settings.milvus_uri, db_name=settings.milvus_db)
        names = client.list_collections()
        for name in names:
            stats = client.get_collection_stats(name)
            result["collections"].append({"name": name, "stats": stats})
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="导出 Milvus 集合元数据")
    parser.add_argument(
        "--out",
        default=str(ROOT / "backups" / f"milvus_meta_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"),
    )
    args = parser.parse_args()
    meta = export_metadata(Path(args.out))
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0 if not meta.get("error") else 1


if __name__ == "__main__":
    raise SystemExit(main())
