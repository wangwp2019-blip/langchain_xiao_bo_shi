#!/usr/bin/env python3
"""Milvus 备份入口：volume 快照 + 元数据导出。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Milvus 自动化备份")
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "backups"),
        help="备份输出目录",
    )
    parser.add_argument(
        "--meta-only",
        action="store_true",
        help="仅导出集合元数据（不打包 Docker volume）",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    meta_script = ROOT / "scripts" / "backup" / "milvus_export.py"
    meta_out = out_dir / f"milvus_meta_{ts}.json"
    subprocess.run([sys.executable, str(meta_script), "--out", str(meta_out)], check=False)

    if args.meta_only:
        print(f"元数据已导出: {meta_out}")
        return 0

    shell_script = ROOT / "scripts" / "backup" / "milvus.sh"
    if sys.platform == "win32":
        print("Windows 环境请使用 WSL/Git Bash 执行 milvus.sh，或使用 --meta-only")
        return 0

    archive = out_dir / f"milvus_{ts}.tar.gz"
    subprocess.run(["bash", str(shell_script), str(archive)], check=True)
    print(f"备份完成: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
