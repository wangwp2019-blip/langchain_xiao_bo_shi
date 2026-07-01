"""学习域外拒答 + 拉回（P0 safety-dialog）。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from ..config import settings

_SAFETY_FILE = settings.base_dir / "deploy" / "learning" / "student_safety.yaml"


@dataclass
class SafetyCheckResult:
    allowed: bool
    reason_code: str
    redirect_message: str | None = None


@lru_cache(maxsize=1)
def _config() -> dict:
    if not _SAFETY_FILE.is_file():
        return {"enabled": True, "off_topic_patterns": [], "redirect_template": ""}
    return yaml.safe_load(_SAFETY_FILE.read_text(encoding="utf-8")) or {}


def check_user_message(text: str, subject: str = "数学") -> SafetyCheckResult:
    cfg = _config()
    if not cfg.get("enabled", True):
        return SafetyCheckResult(True, "disabled")
    msg = (text or "").strip()
    if not msg:
        return SafetyCheckResult(True, "empty")
    for pat in cfg.get("off_topic_patterns") or []:
        if re.search(pat, msg, re.IGNORECASE):
            tmpl = cfg.get("redirect_template") or "我们继续学习吧～"
            empathy = "我理解你的想法，"
            redirect = tmpl.format(empathy=empathy, subject=subject)
            return SafetyCheckResult(False, "off_topic", redirect)
    return SafetyCheckResult(True, "ok")
