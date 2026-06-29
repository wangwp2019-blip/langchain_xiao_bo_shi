"""备份恢复脚本存在性与 verify 模式校验（不启动数据库）。"""

from __future__ import annotations

import gzip
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RESTORE = ROOT / "scripts" / "backup" / "restore-all.sh"
ENTRYPOINT = ROOT / "deploy" / "prometheus" / "alertmanager-entrypoint.sh"


def _bash_available() -> bool:
    return shutil.which("bash") is not None


def _run_bash(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def test_restore_script_has_targets():
    text = RESTORE.read_text(encoding="utf-8")
    assert "verify_backup" in text
    assert "restore_postgres" in text
    assert "restore_mysql" in text
    for target in ("verify", "postgres", "mysql"):
        assert target in text


def test_alertmanager_entrypoint_exists():
    text = ENTRYPOINT.read_text(encoding="utf-8")
    assert "ALERTMANAGER_WEBHOOK_URL" in text
    assert "ALERTMANAGER_SLACK_WEBHOOK" in text
    assert "/bin/alertmanager" in text


@pytest.mark.skipif(sys.platform == "win32", reason="bash 集成测在 Linux CI 执行")
@pytest.mark.skipif(not _bash_available(), reason="需要 bash")
def test_restore_script_verify_postgres_dump(tmp_path: Path):
    gz = tmp_path / "postgres_e2e.sql.gz"
    with gzip.open(gz, "wt", encoding="utf-8") as f:
        f.write("-- PostgreSQL database dump\n")
        f.write("SELECT 1;\n")

    proc = _run_bash(str(RESTORE), "verify", str(gz))
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "verify 完成" in proc.stdout


@pytest.mark.skipif(sys.platform == "win32", reason="bash 集成测在 Linux CI 执行")
@pytest.mark.skipif(not _bash_available(), reason="需要 bash")
def test_restore_script_usage_exits_nonzero():
    proc = _run_bash(str(RESTORE))
    assert proc.returncode != 0
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert "用法" in combined
