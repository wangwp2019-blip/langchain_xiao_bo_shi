"""KP 审核：upload → diff → approve（P1 kp-review 简化 Web 版）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import kp_catalog, storage
from .kp_catalog import UnitCatalogEntry, _parse_kp_file, load_catalog


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jobs() -> list[dict]:
    return storage.load_global_list("kp_review_jobs.json")


def _save_jobs(jobs: list[dict]) -> None:
    storage.save_global_list("kp_review_jobs.json", jobs)


def submit_kp_document(path: Path, submitted_by: str = "teacher") -> dict:
    units = _parse_kp_file(path)
    job_id = f"kpjob-{uuid.uuid4().hex[:10]}"
    diff = compute_diff(units)
    job = {
        "job_id": job_id,
        "path": str(path),
        "submitted_by": submitted_by,
        "status": "pending_review",
        "units": [u.model_dump() for u in units],
        "diff": diff,
        "created_at": _now(),
        "ready_to_approve": diff.get("blocking_count", 0) == 0,
    }
    jobs = _jobs()
    jobs.append(job)
    _save_jobs(jobs)
    return job


def submit_kp_text(content: str, filename: str = "upload.kp.md") -> dict:
    tmp = storage.learning_dir() / f"_upload_{uuid.uuid4().hex[:8]}.kp.md"
    tmp.write_text(content, encoding="utf-8")
    return submit_kp_document(tmp)


def get_job(job_id: str) -> dict | None:
    for j in _jobs():
        if j.get("job_id") == job_id:
            return j
    return None


def compute_diff(draft_units: list[UnitCatalogEntry]) -> dict:
    catalog = {u.unit_id: u for u in load_catalog()}
    changes: list[dict] = []
    blocking = 0
    for du in draft_units:
        cu = catalog.get(du.unit_id)
        if not cu:
            changes.append({"type": "new_unit", "unit_id": du.unit_id, "title": du.unit_title})
            continue
        draft_kps = {k.knowledge_point_id: k for k in du.knowledge_points}
        cat_kps = {k.knowledge_point_id: k for k in cu.knowledge_points}
        for kid, kp in draft_kps.items():
            if kid not in cat_kps:
                changes.append({"type": "new_kp", "kp_id": kid, "title": kp.title})
            elif cat_kps[kid].title != kp.title:
                changes.append(
                    {
                        "type": "title_changed",
                        "kp_id": kid,
                        "old": cat_kps[kid].title,
                        "new": kp.title,
                    }
                )
                blocking += 1
        for kid in cat_kps:
            if kid not in draft_kps:
                changes.append({"type": "missing_in_draft", "kp_id": kid, "title": cat_kps[kid].title})
                blocking += 1
    return {"changes": changes, "blocking_count": blocking}


def approve_job(job_id: str) -> dict:
    job = get_job(job_id)
    if not job:
        raise KeyError(job_id)
    override_path = storage.learning_dir() / "catalog_override.json"
    import json

    override_path.write_text(json.dumps(job.get("units", []), ensure_ascii=False, indent=2), encoding="utf-8")
    kp_catalog.reload_catalog()
    job["status"] = "approved"
    job["approved_at"] = _now()
    jobs = _jobs()
    for i, j in enumerate(jobs):
        if j.get("job_id") == job_id:
            jobs[i] = job
    _save_jobs(jobs)
    return job


def list_jobs(status: str | None = None) -> list[dict]:
    jobs = _jobs()
    if status:
        jobs = [j for j in jobs if j.get("status") == status]
    return sorted(jobs, key=lambda x: x.get("created_at", ""), reverse=True)
