"""学习域 JSON 持久化（与 privacy consent 同模式）。"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from ..config import settings

_lock = threading.Lock()


def learning_dir() -> Path:
    path = settings.memory_dir / "learning"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load(name: str) -> dict[str, Any]:
    path = learning_dir() / name
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(name: str, data: dict[str, Any]) -> None:
    path = learning_dir() / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_student_bucket(name: str, student_id: str) -> list[dict[str, Any]]:
    with _lock:
        data = _load(name)
        return list(data.get(student_id, []))


def append_student_record(name: str, student_id: str, record: dict[str, Any]) -> None:
    with _lock:
        data = _load(name)
        bucket = data.setdefault(student_id, [])
        bucket.append(record)
        _save(name, data)


def upsert_student_singleton(name: str, student_id: str, record: dict[str, Any]) -> None:
    with _lock:
        data = _load(name)
        data[student_id] = record
        _save(name, data)


def get_student_singleton(name: str, student_id: str) -> dict[str, Any] | None:
    with _lock:
        data = _load(name)
        row = data.get(student_id)
        return row if isinstance(row, dict) else None


def load_global_list(name: str) -> list[dict[str, Any]]:
    with _lock:
        data = _load(name)
        if isinstance(data, list):
            return data
        return data.get("_items", [])


def save_global_list(name: str, items: list[dict[str, Any]]) -> None:
    with _lock:
        _save(name, {"_items": items})


def clear_learning_for_tests() -> None:
    with _lock:
        for f in learning_dir().glob("*.json"):
            f.unlink(missing_ok=True)
