"""适龄行为档（behavior.yaml）注入 System Prompt。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from ..config import settings

_BEHAVIOR_FILE = settings.base_dir / "deploy" / "learning" / "behavior.yaml"


@lru_cache(maxsize=1)
def _load() -> dict:
    if not _BEHAVIOR_FILE.is_file():
        return {"profiles": {"default": {"tone": "warm"}}}
    return yaml.safe_load(_BEHAVIOR_FILE.read_text(encoding="utf-8")) or {}


def format_behavior_prompt(grade_level: int | None = None) -> str:
    data = _load()
    profiles = data.get("profiles") or {}
    key = f"grade_{grade_level}" if grade_level else "default"
    prof = profiles.get(key) or profiles.get("default") or {}
    rules = prof.get("rules") or []
    lines = ["【学伴行为档】", f"- 语气：{prof.get('tone', 'warm')} · 句子简短 · 先共情"]
    for r in rules:
        lines.append(f"- {r}")
    return "\n".join(lines)
