"""Milvus 备份元数据导出测试。"""

from __future__ import annotations

import json
from pathlib import Path

import app.config as cfg


def test_milvus_export_skips_non_milvus_backend(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg.settings, "vector_backend", "keyword")
    out = tmp_path / "meta.json"

    import importlib.util

    script = Path(__file__).resolve().parents[1] / "scripts" / "backup" / "milvus_export.py"
    spec = importlib.util.spec_from_file_location("milvus_export", script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    result = mod.export_metadata(out)
    assert result["skipped"] is True
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["vector_backend"] == "keyword"


def test_run_milvus_backup_meta_only(tmp_path):
    import subprocess
    import sys

    out_dir = tmp_path / "backups"
    proc = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "run_milvus_backup.py"),
            "--meta-only",
            "--out-dir",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert proc.returncode == 0
    assert list(out_dir.glob("milvus_meta_*.json"))
