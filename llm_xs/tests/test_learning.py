"""Jarvis 学习域 API 与学情闭环测试。"""

from __future__ import annotations

import pytest

from app.learning import storage
from app.learning import attempt_service, gap_service, kp_catalog, photo_service, plan_service
from app.learning.schemas import FreeformAttemptRequest, PhotoClassifyRequest


@pytest.fixture(autouse=True)
def _clean_learning():
    storage.clear_learning_for_tests()
    kp_catalog.reload_catalog()
    yield
    storage.clear_learning_for_tests()


def test_kp_catalog_loads():
    units = kp_catalog.list_units(grade_level=2)
    assert len(units) >= 1
    unit = kp_catalog.get_unit(units[0].unit_id)
    assert len(unit.knowledge_points) >= 1


def test_onboarding_and_attempt_flow(client):
    sid = "learn-test-kid"
    r = client.post(
        "/api/learning/onboarding",
        params={"user_id": sid},
        json={"grade": "二年级", "subject": "数学", "unit_id": "math-g2-add-sub-100"},
    )
    assert r.status_code == 200
    assert r.json()["profile"]["grade_level"] == 2

    att = client.post(
        "/api/learning/attempts",
        params={"user_id": sid},
        json={"question_id": "q-g2-borrow-01", "answer": "25"},
    )
    assert att.status_code == 200
    assert att.json()["attempt"]["is_correct"] is True

    gaps = client.get("/api/learning/gaps", params={"user_id": sid})
    assert gaps.status_code == 200


def test_freeform_attempt(client):
    sid = "freeform-kid"
    client.post(
        "/api/learning/onboarding",
        params={"user_id": sid},
        json={"grade": "二年级", "subject": "数学"},
    )
    r = client.post(
        "/api/learning/attempts/freeform",
        params={"user_id": sid},
        json={"prompt": "15 + 8 = ?", "student_answer": "23"},
    )
    assert r.status_code == 200
    assert r.json()["attempt"]["is_correct"] is True


def test_suggest_questions(client):
    sid = "suggest-kid"
    r = client.post(
        "/api/learning/questions/suggest",
        params={"user_id": sid},
        json={"count": 2, "weak_only": False},
    )
    assert r.status_code == 200
    assert len(r.json()["questions"]) >= 1


def test_photo_classify_inbox(client):
    sid = "photo-kid"
    r = client.post(
        "/api/learning/photo/classify",
        params={"user_id": sid},
        json={"text": "52-27 退位减法竖式", "subject": "数学"},
    )
    assert r.status_code == 200
    assert r.json()["triage"] in ("auto", "inbox", "explain_only")


def test_parent_report(client):
    sid = "report-kid"
    attempt_service.onboard(sid, "二年级", "数学", "math-g2-add-sub-100", None)
    attempt_service.submit_bank_attempt(sid, "q-g2-carry-01", "65")
    r = client.get(f"/api/parent/students/{sid}/report")
    assert r.status_code == 200
    body = r.json()
    assert "summary" in body
    assert "dimension_scores" in body


def test_study_plan(client):
    sid = "plan-kid"
    r = client.post("/api/learning/plan", params={"user_id": sid})
    assert r.status_code == 200
    assert len(r.json()["plan"]["steps"]) >= 1


def test_progress_view(client):
    sid = "prog-kid"
    r = client.get("/api/learning/progress", params={"user_id": sid})
    assert r.status_code == 200
    assert "encouragement" in r.json()


def test_kp_catalog_api(client):
    r = client.get("/api/kp/catalog", params={"grade": 2})
    assert r.status_code == 200
    assert len(r.json()["units"]) >= 1


def test_vision_understand(client):
    sid = "vision-kid"
    r = client.post(
        "/api/learning/vision/understand",
        params={"user_id": sid},
        json={"text": "52-27=25\n37+28=65", "mode": "homework"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["vision_id"].startswith("vis-")
    assert len(body["items"]) >= 1


def test_push_queue(client):
    sid = "push-kid"
    attempt_service.onboard(sid, "二年级", "数学", "math-g2-add-sub-100", None)
    attempt_service.submit_bank_attempt(sid, "q-g2-borrow-01", "99")
    r = client.post(
        "/api/learning/push-queue/rebuild",
        params={"user_id": sid},
        json={"count": 3},
    )
    assert r.status_code == 200
    peek = client.get("/api/learning/push-queue", params={"user_id": sid})
    assert peek.status_code == 200


def test_kp_review_submit(client):
    content = """---
学科: 数学
年级: 2
---
# 单元：测试单元
unit_id: math-g2-test-unit
## 知识点
- 测试知识点 → kp-g2-test-kp
"""
    r = client.post("/api/kp-review/submit", json={"content": content})
    assert r.status_code == 200
    assert r.json()["job_id"].startswith("kpjob-")


def test_dimensions(client):
    sid = "dim-kid"
    r = client.get("/api/learning/dimensions", params={"user_id": sid})
    assert r.status_code == 200
    assert "scores" in r.json()


def test_question_bank_size():
    from app.learning.question_bank import _BANK

    assert len(_BANK) >= 30
