"""快速冒烟：验证学习域所有新端点可用（开放模式，无鉴权）。"""

from __future__ import annotations

import os

os.environ["KIDS_API_KEYS"] = ""
os.environ["KIDS_REQUIRE_AUTH"] = "false"
os.environ["KIDS_REQUIRE_PARENT_CONSENT"] = "false"
os.environ["KIDS_JWT_SECRET"] = ""

import app.config as cfg  # noqa: E402

cfg.settings.api_keys = None
cfg.settings.require_auth = False
cfg.settings.require_parent_consent = False
cfg.settings.jwt_secret = None
cfg.settings.api_rate_limit_per_min = 1000

from fastapi.testclient import TestClient  # noqa: E402

from app.api import app  # noqa: E402
from app.learning import storage  # noqa: E402

storage.clear_learning_for_tests()

with TestClient(app) as c:
    sid = "smoke-kid"
    # onboarding
    r = c.post("/api/learning/onboarding", params={"user_id": sid}, json={"grade": "二年级", "subject": "数学"})
    assert r.status_code == 200, r.text
    print("onboarding ok")

    # bank attempt
    r = c.post("/api/learning/attempts", params={"user_id": sid}, json={"question_id": "q-g2-borrow-01", "answer": "25"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["attempt"]["is_correct"]
    assert "proactive_message" in body
    print("attempt + proactive ok")

    # freeform
    r = c.post("/api/learning/attempts/freeform", params={"user_id": sid}, json={"prompt": "15+8=?", "student_answer": "23"})
    assert r.status_code == 200, r.text
    print("freeform ok")

    # gaps
    r = c.get("/api/learning/gaps", params={"user_id": sid})
    assert r.status_code == 200
    print("gaps ok:", len(r.json()["gaps"]))

    # suggest
    r = c.post("/api/learning/questions/suggest", params={"user_id": sid}, json={"count": 2, "weak_only": False})
    assert r.status_code == 200
    print("suggest ok:", len(r.json()["questions"]))

    # plan
    r = c.post("/api/learning/plan", params={"user_id": sid})
    assert r.status_code == 200
    print("plan ok:", len(r.json()["plan"]["steps"]))

    # progress
    r = c.get("/api/learning/progress", params={"user_id": sid})
    assert r.status_code == 200
    print("progress ok")

    # dimensions
    r = c.get("/api/learning/dimensions", params={"user_id": sid})
    assert r.status_code == 200
    print("dimensions ok:", r.json()["scores"])

    # proactive
    r = c.get("/api/learning/proactive", params={"user_id": sid})
    assert r.status_code == 200
    print("proactive ok")

    # remediation
    r = c.get("/api/learning/remediation", params={"user_id": sid})
    assert r.status_code == 200
    print("remediation ok")

    # photo classify
    r = c.post("/api/learning/photo/classify", params={"user_id": sid}, json={"text": "52-27 退位减法", "subject": "数学"})
    assert r.status_code == 200
    print("photo classify ok:", r.json()["triage"])

    # vision understand
    r = c.post("/api/learning/vision/understand", params={"user_id": sid}, json={"text": "52-27=25", "mode": "graded"})
    assert r.status_code == 200
    print("vision ok:", r.json()["vision_id"])

    # push queue
    r = c.post("/api/learning/push-queue/rebuild", params={"user_id": sid}, json={"count": 3})
    assert r.status_code == 200
    r = c.get("/api/learning/push-queue", params={"user_id": sid})
    assert r.status_code == 200
    print("push queue ok:", len(r.json()["questions"]))

    # wiki
    r = c.get("/api/learning/wiki/search", params={"q": "退位"})
    assert r.status_code == 200
    print("wiki search ok:", len(r.json()["hits"]))

    # kp catalog
    r = c.get("/api/kp/catalog", params={"grade": 2})
    assert r.status_code == 200
    print("kp catalog ok:", len(r.json()["units"]))

    # parent
    r = c.get(f"/api/parent/students/{sid}/profile")
    assert r.status_code == 200
    print("parent profile ok")

    r = c.get(f"/api/parent/students/{sid}/report")
    assert r.status_code == 200
    print("parent report ok")

    # kp review
    r = c.post("/api/kp-review/submit", json={"content": "---\n学科: 数学\n年级: 2\n---\n# 单元：测试\nunit_id: math-g2-test\n## 知识点\n- 测试 → kp-g2-test\n"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    print("kp review submit ok:", job_id)

    r = c.get("/api/kp-review/jobs")
    assert r.status_code == 200
    print("kp review jobs ok:", len(r.json()["jobs"]))

    # textbook ingest
    r = c.post("/api/kp-review/ingest/submit", json={"content": "第二单元 100以内加减法\n进位加法 退位减法", "source_type": "document", "grade_level": 2, "subject": "数学"})
    assert r.status_code == 200, r.text
    ingest_id = r.json()["job_id"]
    print("ingest submit ok:", ingest_id)

    r = c.get("/api/kp-review/ingest/jobs")
    assert r.status_code == 200
    print("ingest jobs ok:", len(r.json()["jobs"]))

    r = c.post(f"/api/kp-review/ingest/jobs/{ingest_id}/promote")
    assert r.status_code == 200, r.text
    print("ingest promote ok:", r.json()["status"])

    # parent report with new fields
    r = c.get(f"/api/parent/students/{sid}/report")
    assert r.status_code == 200
    rep = r.json()
    assert "attempts_total" in rep
    assert "correct_rate" in rep
    print("report new fields ok:", rep["attempts_total"], rep["correct_rate"])

storage.clear_learning_for_tests()
print("\n=== ALL SMOKE TESTS PASSED ===")
