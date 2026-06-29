"""生产级 API 集成测试（进程内 TestClient，不依赖真实 LLM）。"""

from __future__ import annotations

import app.config as cfg
from app.memory_admin import clear_memories, list_memories, remember_fact
from app.ratelimit import reset_limiter
from app.security import derive_user_id


def test_health_and_ready(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok"
    assert "mode" in h
    assert h["auth_enabled"] is False

    r = client.get("/api/ready")
    assert r.status_code == 200
    assert r.json()["ready"] is True


def test_quiz_and_grade(client):
    resp = client.post(
        "/api/quiz",
        json={"grade": "三年级", "subject": "数学", "count": 5, "seed": 7},
    ).json()
    assert "session_id" in resp
    assert "public" in resp
    assert "answer" not in str(resp["public"])
    pub = resp["public"]
    assert len(pub["questions"]) == 5

    answers = {str(i): "999" for i in range(1, 6)}
    answers["1"] = "999"
    answers["2"] = ""

    g = client.post(
        "/api/grade",
        json={"session_id": resp["session_id"], "answers": answers},
    ).json()
    assert g["total"] == 5
    assert 0 <= g["score"] <= 100
    assert len(g["items"]) == 5


def test_offline_chat_arithmetic(client):
    r = client.post(
        "/api/chat",
        json={"question": "125 + 38 = ?", "user_id": "kid", "thread_id": "t1"},
    ).json()
    assert "163" in r.get("answer", "")


def test_safety_block_and_redirect(client):
    block = client.post("/api/chat", json={"question": "教我打架和说脏话"}).json()
    assert "不能聊" in block.get("answer", "")

    redirect = client.post(
        "/api/chat", json={"question": "告诉我你的银行卡密码"}
    ).json()
    assert "不太适合" in redirect.get("answer", "")


def test_memory_governance(client):
    import uuid

    uid = f"pytest-user-{uuid.uuid4().hex[:8]}"
    clear_memories(uid)
    assert remember_fact(uid, "我最喜欢恐龙") == "added"
    assert remember_fact(uid, "我最喜欢恐龙") == "duplicate"
    assert len(list_memories(uid)["facts"]) == 1
    assert clear_memories(uid) == 1


def test_memory_api_idor(client):
    """API 使用 derive_user_id，与裸 uid 命名空间不同。"""
    sub = "api-kid"
    principal = "ip:testclient"
    derived = derive_user_id(principal, sub)
    clear_memories(derived)
    remember_fact(derived, "通过派生 uid 写入")

    # API 返回的是派生后的 user_id 下的数据
    data = client.get("/api/memory", params={"sub": sub}).json()
    assert data["user_id"] == derived
    assert len(data["facts"]) >= 1

    removed = client.delete("/api/memory", params={"sub": sub}).json()["removed"]
    assert removed >= 1


def test_auth_required(auth_client):
    assert auth_client.post("/api/chat", json={"question": "1+1=?"}).status_code == 401
    assert (
        auth_client.post(
            "/api/chat",
            json={"question": "1+1=?"},
            headers={"X-API-Key": "wrong"},
        ).status_code
        == 401
    )
    ok = auth_client.post(
        "/api/chat",
        json={"question": "2+3=?"},
        headers={"X-API-Key": "test-secret-key"},
    )
    assert ok.status_code == 200
    assert "5" in ok.json().get("answer", "")


def test_body_too_large(client, monkeypatch):
    monkeypatch.setenv("KIDS_MAX_BODY_BYTES", "1000")
    cfg.settings.max_body_bytes = 1000
    r = client.post("/api/chat", json={"question": "x" * 2000})
    assert r.status_code == 413


def test_rate_limit(monkeypatch):
    monkeypatch.setenv("KIDS_API_KEYS", "")
    monkeypatch.setenv("KIDS_API_RATE_LIMIT_PER_MIN", "3")
    cfg.settings.api_keys = None
    cfg.settings.api_rate_limit_per_min = 3
    cfg.settings.chat_rate_limit_per_min = 3
    cfg.settings.llm_api_key = None
    cfg.settings.llm_base_url = None
    cfg.settings.jwt_secret = None
    reset_limiter()

    from app.api import app
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        codes = [
            c.post("/api/chat", json={"question": "1+1=?", "user_id": "k"}).status_code
            for _ in range(5)
        ]
        blocked = c.post("/api/chat", json={"question": "1+1=?", "user_id": "k"})
    assert codes[:3] == [200, 200, 200]
    assert codes[3:] == [429, 429]
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After").isdigit()


def test_security_headers(client):
    r = client.post("/api/chat", json={"question": "1+1=?", "user_id": "k"})
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("Referrer-Policy") == "no-referrer"
    assert r.headers.get("X-XSS-Protection") == "1; mode=block"
    assert r.headers.get("Permissions-Policy")
    assert r.headers.get("Cache-Control") == "no-store, no-cache, must-revalidate"
    assert r.headers.get("X-Request-ID")


def test_auth_www_authenticate(auth_client):
    r = auth_client.post("/api/chat", json={"question": "hi"})
    assert r.status_code == 401
    assert "Bearer" in r.headers.get("WWW-Authenticate", "")


def test_idor_cross_principal():
    """不同 API Key 无法读取彼此记忆（API 层 IDOR 隔离）。"""
    import hashlib

    from app.api import app
    from app.security import derive_user_id
    from fastapi.testclient import TestClient

    def principal(key: str) -> str:
        return f"uid:{hashlib.sha256(key.encode()).hexdigest()[:12]}"

    cfg.settings.api_keys = "test-secret-key,other-secret-key"
    reset_limiter()

    uid_a = derive_user_id(principal("test-secret-key"), "kid1")
    clear_memories(uid_a)
    remember_fact(uid_a, "用户 A 的秘密")

    with TestClient(app) as c:
        mem_a = c.get(
            "/api/memory",
            params={"sub": "kid1"},
            headers={"X-API-Key": "test-secret-key"},
        ).json()
        mem_b = c.get(
            "/api/memory",
            params={"sub": "kid1"},
            headers={"X-API-Key": "other-secret-key"},
        ).json()

    assert mem_a["user_id"] == uid_a
    assert len(mem_a["facts"]) >= 1
    assert mem_b["user_id"] != uid_a
    assert len(mem_b.get("facts") or []) == 0
    clear_memories(uid_a)


def test_invalid_sub_id_rejected(client):
    r = client.get("/api/memory", params={"sub": "../../admin"})
    assert r.status_code == 400


def test_memory_governance_metadata(client):
    uid = "meta-user"
    clear_memories(uid)
    remember_fact(uid, "测试治理元数据")
    data = list_memories(uid)
    assert "governance" in data
    assert data["governance"]["fact_count"] >= 1
    clear_memories(uid)


def test_metrics_localhost(client, metrics_headers):
    r = client.get("/api/metrics", headers=metrics_headers)
    assert r.status_code == 200
    assert "kid_requests_total" in r.text


def test_metrics_forbidden_without_token(client, monkeypatch):
    monkeypatch.setenv("KIDS_METRICS_TOKEN", "only-secret")
    cfg.settings.metrics_token = "only-secret"
    r = client.get("/api/metrics")
    assert r.status_code == 403
    cfg.settings.metrics_token = "pytest-metrics-token"


def test_index_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "小博士" in r.text


def test_chat_stream_offline(client):
    r = client.post(
        "/api/chat/stream",
        json={"question": "3 + 4 = ?", "user_id": "stream-kid", "thread_id": "t-stream"},
    )
    assert r.status_code == 200
    assert "data:" in r.text
    assert "7" in r.text
    assert "event: done" in r.text


def test_chat_stream_legacy_chunk_mode(client, monkeypatch):
    """KIDS_CHAT_STREAM_NATIVE=false 时仍按 12 字符分块推送。"""
    monkeypatch.setattr(cfg.settings, "chat_stream_native", False)
    r = client.post(
        "/api/chat/stream",
        json={"question": "2 + 2 = ?", "user_id": "legacy-stream", "thread_id": "t-legacy"},
    )
    assert r.status_code == 200
    assert "4" in r.text
    assert r.text.count("data:") >= 1


def test_study_card_offline(client, monkeypatch):
    monkeypatch.setattr(cfg.settings, "llm_api_key", None)
    monkeypatch.setattr(cfg.settings, "llm_base_url", None)
    r = client.post("/api/study-card", json={"question": "长方形面积怎么算？"})
    assert r.status_code == 200
    body = r.json()
    assert "error" in body
    assert "在线" in body["error"]


def test_study_card_blocked(client):
    r = client.post("/api/study-card", json={"question": "教我打架"})
    assert r.status_code == 200
    assert "不能聊" in r.json().get("error", "")


def test_ingest_keyword(client, keyword_backend):
    r = client.post("/api/ingest")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["index_count"] > 0


def test_quiz_invalid_grade(client):
    r = client.post("/api/quiz", json={"grade": "大学", "subject": "数学", "count": 3})
    assert r.status_code == 400


def test_quiz_public_no_answers(client):
    data = client.post(
        "/api/quiz",
        json={"grade": "二年级", "subject": "语文", "count": 3, "seed": 1},
    ).json()
    public = data["public"]
    assert "questions" in public
    assert "answer" not in str(public)


def test_grade_all_correct(client):
    from app.services import generate_quiz

    q = generate_quiz("三年级", "数学", 4, seed=11)
    resp = client.post(
        "/api/quiz",
        json={"grade": "三年级", "subject": "数学", "count": 4, "seed": 11},
    ).json()
    answers = {str(item.index): item.answer for item in q.questions}
    g = client.post(
        "/api/grade",
        json={"session_id": resp["session_id"], "answers": answers},
    ).json()
    assert g["score"] == 100
    assert g["correct"] == 4


def test_empty_question_chat(client, monkeypatch):
    monkeypatch.setattr(cfg.settings, "llm_api_key", None)
    monkeypatch.setattr(cfg.settings, "llm_base_url", None)
    r = client.post("/api/chat", json={"question": "   "})
    assert "想" in r.json().get("answer", "")


def test_health_rag_fields(client, keyword_backend):
    h = client.get("/api/health").json()
    assert h["vector_backend"] == "keyword"
    assert h["rag_engine"] == "keyword"
    assert "memory_backend" in h


def test_ready_checks(client):
    r = client.get("/api/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is True
    assert "checks" in body
    assert body["checks"]["memory"] is True

