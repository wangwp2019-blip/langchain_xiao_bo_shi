"""教材 Ingest 简化版（P0 stub）：接收文本/路径 → 生成 job → pending_review。

完整 PDF/OCR 解析不在 P0 范围；本模块只做「记录 + 预览 + KP 候选占位」，
审核流复用 `kp_review`（approve 后写入 catalog override）。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import storage


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jobs() -> list[dict]:
    return storage.load_global_list("textbook_ingest_jobs.json")


def _save_jobs(jobs: list[dict]) -> None:
    storage.save_global_list("textbook_ingest_jobs.json", jobs)


def submit_text(
    content: str,
    *,
    source_type: str = "document",
    grade_level: int = 2,
    subject: str | None = None,
    unit_id_hint: str | None = None,
) -> dict:
    """接收教材文本（PDF 抽取/拍照 OCR/文档粘贴），生成 ingest job。

    Args:
        content: 教材文本内容
        source_type: pdf / photo / document
        grade_level: 年级
        subject: 学科
        unit_id_hint: 可选单元 ID 提示
    """
    job_id = f"ing-{uuid.uuid4().hex[:10]}"
    preview = content[:500]
    job = {
        "job_id": job_id,
        "source_type": source_type,
        "source_path": "",
        "status": "pending_review",
        "grade_level": grade_level,
        "subject": subject,
        "unit_id_hint": unit_id_hint,
        "extracted_text_preview": preview,
        "kp_candidates": [],
        "created_at": _now(),
    }
    jobs = _jobs()
    jobs.append(job)
    _save_jobs(jobs)
    return job


def submit_file(path: Path, *, source_type: str = "pdf", grade_level: int = 2, subject: str | None = None) -> dict:
    """接收文件路径，读取文本（若可读）生成 job。"""
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        content = f"（文件 {path} 无法读取，待 OCR/解析）"
    return submit_text(
        content,
        source_type=source_type,
        grade_level=grade_level,
        subject=subject,
    )


def list_jobs(status: str | None = None) -> list[dict]:
    jobs = _jobs()
    if status:
        jobs = [j for j in jobs if j.get("status") == status]
    return sorted(jobs, key=lambda x: x.get("created_at", ""), reverse=True)


def get_job(job_id: str) -> dict | None:
    for j in _jobs():
        if j.get("job_id") == job_id:
            return j
    return None


def promote_to_kp_review(job_id: str) -> dict:
    """将 ingest job 的文本预览提交到 KP 审核流，转为 kp_review job。"""
    from . import kp_review

    job = get_job(job_id)
    if not job:
        raise KeyError(job_id)
    review_job = kp_review.submit_kp_text(
        job.get("extracted_text_preview", ""),
        filename=f"ingest-{job_id}.kp.md",
    )
    job["status"] = "promoted_to_review"
    job["kp_review_job_id"] = review_job["job_id"]
    jobs = _jobs()
    for i, j in enumerate(jobs):
        if j.get("job_id") == job_id:
            jobs[i] = job
    _save_jobs(jobs)
    return job
