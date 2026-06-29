"""FastAPI 线上服务（生产级）。

端点：
- ``GET  /``                  内嵌儿童风格聊天网页
- ``GET  /api/health``        健康检查（liveness + 当前后端状态）
- ``GET  /api/ready``         就绪探针（真探测依赖：索引/记忆）
- ``GET  /api/metrics``       Prometheus 指标（可选 Token 保护）
- ``POST /api/chat``          一次性问答（安全护栏 + 离线降级）
- ``POST /api/chat/stream``   SSE 流式问答（服务端先跑完护栏再分块推送）
- ``POST /api/study-card``    结构化学习卡片
- ``POST /api/quiz``          按年级+学科出题
- ``POST /api/grade``         判分
- ``GET  /api/memory``        查看长期记忆（鉴权 + 防越权）
- ``DELETE /api/memory``      清除长期记忆
- ``GET  /api/privacy/policy``     隐私政策与家长权利说明
- ``GET  /api/privacy/consent``    查询家长同意状态
- ``POST /api/privacy/consent``    记录家长同意
- ``DELETE /api/privacy/account``  删除用户全部数据
- ``POST /api/privacy/retention/sweep``  数据留存清理（Cron/Token）

生产级中间件：请求 ID、访问日志、请求体大小限制、安全响应头、限流、指标。
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    StreamingResponse,
)
from pydantic import BaseModel, Field

from . import metrics
from .audit import memory_access, rate_limited
from .audit_persist import persist_chat_log, persist_quiz_record
from .config import settings
from .http_security import apply_security_headers, read_body_with_limit
from .logging_setup import configure_logging
from .ratelimit import get_chat_limiter, get_limiter
from .safety import check_input, sanitize_output
from .security import (
    authenticate,
    client_id_from_request,
    compare_secret,
    derive_thread_id,
    derive_user_id,
    verify_ingest_token,
)

logger = logging.getLogger(__name__)

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)

_KID_FRIENDLY_ERROR = (
    "小朋友，小博士这会儿有点忙，请稍后再试，或者问问老师、家长好不好？"
)

_KID_QUOTA_MESSAGE = (
    "小朋友，今天和小博士聊得已经很多啦～🌙 先去休息或复习一下，明天再来找我吧！"
)


def _kid_friendly_error(exc: Exception) -> str:
    logger.exception("[req=%s] API 处理失败: %s", request_id_var.get(), exc)
    return _KID_FRIENDLY_ERROR


def _enforce_llm_quota(principal: str) -> JSONResponse | None:
    """在线大模型调用前检查每日配额；超限返回 429，否则 None。"""
    if not settings.llm_configured:
        return None
    from .quota import QuotaExceeded, check_and_consume

    try:
        check_and_consume(principal)
        return None
    except QuotaExceeded as q:
        return JSONResponse(
            status_code=429,
            content={"error": _KID_QUOTA_MESSAGE},
            headers={"Retry-After": str(q.retry_after)},
        )


# ==================== 请求/响应模型 ====================


class ChatRequest(BaseModel):
    question: str = Field(..., max_length=2000)
    user_id: str = "default-student"
    thread_id: str = "default-thread"


class QuestionRequest(BaseModel):
    question: str = Field(..., max_length=2000)


class QuizRequest(BaseModel):
    grade: str
    subject: str
    count: int = 10
    seed: int | None = None


class GradeRequest(BaseModel):
    session_id: str = Field(..., min_length=8, max_length=128)
    answers: dict[str, str] | list[str]
    # 兼容旧客户端（仅开发环境）：显式传题目+答案时仍可用，生产应禁用
    grade: str | None = None
    subject: str | None = None
    questions: list[dict] | None = None


class ConsentRequest(BaseModel):
    sub: str = "default"
    parent_name: str = Field(..., min_length=1, max_length=64)
    parent_email: str | None = Field(default=None, max_length=128)


# ==================== 生命周期 ====================


def _index_count() -> int:
    try:
        from .knowledge import get_index_count

        return get_index_count()
    except Exception:  # noqa: BLE001
        return 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    prod_errors = settings.validate_production()
    if prod_errors:
        for err in prod_errors:
            logger.error("生产配置检查: %s", err)
        if settings.is_production:
            raise RuntimeError("生产启动门禁未通过: " + "; ".join(prod_errors))
    settings.ensure_dirs()
    count = _index_count()
    if count == 0:
        print("[提示] 知识库索引为空，请先运行：python run_ingest.py")
    else:
        print(f"[就绪] 知识库索引已加载，共 {count} 个片段。")
    print(
        f"[模式] LLM={'在线' if settings.llm_configured else '离线'} | "
        f"RAG={settings.rag_engine} | "
        f"ENV={settings.app_env} | "
        f"鉴权={'开' if settings.auth_enabled else '关'} | "
        f"限流={settings.api_rate_limit_per_min}/min"
    )
    trace_status = __import__("app.tracing", fromlist=["init_tracing"]).init_tracing(app)
    if trace_status.get("langsmith") or trace_status.get("opentelemetry"):
        print(f"[追踪] LangSmith={trace_status.get('langsmith')} OTEL={trace_status.get('opentelemetry')}")
    yield
    from .db import close_pool
    from .mysql_db import close_mysql_pool
    from .tracing import shutdown_tracing

    shutdown_tracing()

    close_pool()
    close_mysql_pool()
    print("[停机] 资源已清理。")


app = FastAPI(
    title="小博士 · 小学生 AI 学习助手",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    # 仅当不是通配来源时才允许携带凭证，避免凭证随通配来源外泄。
    allow_credentials=settings.cors_origin_list != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 中间件 ====================


@app.middleware("http")
async def production_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    request_id_var.set(rid)
    start = time.monotonic()
    path = request.url.path

    # 请求体大小限制（413）
    if request.method in ("POST", "PUT", "PATCH") and path.startswith("/api/"):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit():
            if int(cl) > settings.max_body_bytes:
                resp = JSONResponse(
                    status_code=413,
                    content={"error": "请求内容太大啦，换短一点好不好？"},
                )
                apply_security_headers(resp, path=path, rid=rid)
                _finish_metrics(resp, rid, path, 413, start)
                return resp
        else:
            # 无 Content-Length 时流式读取硬限制，防绕过
            body = await read_body_with_limit(request, settings.max_body_bytes)
            if body is None:
                resp = JSONResponse(
                    status_code=413,
                    content={"error": "请求内容太大啦，换短一点好不好？"},
                )
                apply_security_headers(resp, path=path, rid=rid)
                _finish_metrics(resp, rid, path, 413, start)
                return resp

    # 限流（429）——聊天端点使用更严的 chat 配额
    if path.startswith("/api/") and not path.endswith(("/health", "/ready", "/metrics")):
        client = client_id_from_request(request)
        limiter = (
            get_chat_limiter()
            if path in ("/api/chat", "/api/chat/stream")
            else get_limiter()
        )
        if not limiter.allow(client):
            retry = limiter.retry_after(client)
            rate_limited(client=client, request_id=rid, retry_after=retry)
            resp = JSONResponse(
                status_code=429,
                content={"error": "小朋友，你问得太快啦，休息一下再问好不好？😊"},
            )
            resp.headers["Retry-After"] = str(retry)
            apply_security_headers(resp, path=path, rid=rid)
            _finish_metrics(resp, rid, path, 429, start)
            return resp

    try:
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[req=%s] 未捕获异常: %s", rid, exc)
        response = JSONResponse(
            status_code=500, content={"error": _KID_FRIENDLY_ERROR}
        )

    apply_security_headers(response, path=path, rid=rid)
    _finish_metrics(response, rid, path, response.status_code, start, method=request.method)
    return response


def _finish_metrics(response, rid: str, path: str, status: int, start: float, *, method: str = "GET") -> None:
    duration = time.monotonic() - start
    try:
        metrics.record_request(path, status, duration, method=method)
    except Exception:  # noqa: BLE001
        pass
    logger.info("[req=%s] %s -> %d (%.0fms)", rid, path, status, duration * 1000)


# ==================== 探针 / 指标 ====================


@app.get("/api/health")
def health():
    if not settings.health_public_detail:
        return {"status": "ok", "env": settings.app_env}
    payload = {
        "status": "ok",
        "env": settings.app_env,
        "agent_engine": "langgraph-stategraph",
        "mode": "online" if settings.llm_configured else "offline",
        "index_count": _index_count(),
        "vector_backend": settings.vector_backend,
        "rag_engine": settings.rag_engine,
        "memory_backend": settings.memory_backend,
        "short_term_backend": settings.short_term_backend,
        "llm_model": settings.llm_model,
        "llm_configured": settings.llm_configured,
        "embedding_configured": settings.embedding_configured,
        "web_search_enabled": settings.web_search_enabled,
        "tavily_enabled": settings.tavily_enabled,
        "google_search_enabled": settings.google_search_enabled,
        "moderation_enabled": settings.moderation_configured,
        "auth_enabled": settings.auth_enabled,
        "mysql_configured": settings.mysql_configured,
        "require_parent_consent": settings.require_parent_consent,
        "tracing": {
            "langsmith": settings.enable_tracing,
            "opentelemetry": settings.otel_enabled,
        },
        "quiz_session": __import__(
            "app.services.quiz_session_store", fromlist=["check_quiz_session_ready"]
        ).check_quiz_session_ready(),
        **(
            {"rag": __import__("app.rag.llamaindex_rag", fromlist=["check_rag_ready"]).check_rag_ready()}
            if settings.rag_engine == "llamaindex"
            else {}
        ),
        **(
            {"mysql": __import__("app.mysql_db", fromlist=["check_mysql_ready"]).check_mysql_ready()}
            if settings.mysql_configured
            else {}
        ),
    }
    return payload


@app.get("/api/ready")
def ready():
    """就绪探针：记忆必须可用；RAG 索引状态写入 checks.rag。"""
    checks: dict = {"index": _index_count() > 0, "memory": True}
    if settings.rag_engine == "llamaindex":
        from .rag.llamaindex_rag import check_rag_ready

        rag = check_rag_ready()
        checks["rag"] = rag
        checks["index"] = rag.get("index_count", 0) > 0
    try:
        from .long_term_memory import get_store

        get_store()
    except Exception as exc:  # noqa: BLE001
        checks["memory"] = False
        logger.warning("ready 探针记忆后端异常: %s", exc)
    ok = checks["memory"]
    from .services.quiz_session_store import check_quiz_session_ready

    quiz_sess = check_quiz_session_ready()
    checks["quiz_session"] = quiz_sess
    if settings.quiz_session_backend.lower() in ("redis", "mysql") and not quiz_sess.get("ready"):
        ok = False
    if settings.mysql_configured:
        from .mysql_db import check_mysql_ready

        mysql = check_mysql_ready()
        checks["mysql"] = mysql
        if not mysql.get("ready"):
            ok = False
    status = 200 if ok else 503
    return JSONResponse(status_code=status, content={"ready": ok, "checks": checks})


@app.get("/api/metrics")
def metrics_endpoint(request: Request):
    token = settings.metrics_token
    if token:
        presented = request.headers.get("X-Metrics-Token") or ""
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            presented = presented or auth[7:].strip()
        if not compare_secret(presented, token):
            return PlainTextResponse("forbidden", status_code=403)
    elif request.client and request.client.host not in ("127.0.0.1", "::1", "localhost"):
        # 未配置 Token 时仅放行本机，避免内部指标在公网裸奔。
        return PlainTextResponse("forbidden", status_code=403)
    return PlainTextResponse(metrics.render(), media_type=metrics.content_type())


# ==================== 提示词 / 快捷提问 ====================


@app.get("/api/prompts/suggestions")
async def prompt_suggestions(
    grade: str | None = None,
    lang: str = "zh",
    limit: int = 8,
    principal: str = Depends(authenticate),
):
    """返回适合小学生的快捷提问建议（可按年级筛选）。"""
    from .graph.prompts import get_suggested_prompts

    safe_limit = max(1, min(limit, 20))
    return {
        "prompts": get_suggested_prompts(grade=grade, lang=lang, limit=safe_limit),
    }


# ==================== 对话 ====================


def _answer_with_guardrails(
    question: str,
    user_id: str,
    thread_id: str,
    *,
    principal: str = "-",
) -> str:
    """统一问答流程：清洗 → 输入护栏 → 在线/离线 → 输出净化（同步，CLI 用）。"""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            _answer_with_guardrails_async(question, user_id, thread_id, principal=principal)
        )
    raise RuntimeError("请使用 await _answer_with_guardrails_async() 于 async 路由内")


async def _prepare_chat(
    question: str,
    user_id: str,
    *,
    principal: str = "-",
) -> tuple[str | None, str]:
    """聊天前置：同意 + 输入护栏。返回 (early_reply, cleaned_text)。"""
    from .privacy import consent_denied_message, has_valid_consent
    from .services.text_utils import clean_text

    if not has_valid_consent(user_id):
        return consent_denied_message(), ""

    text = clean_text(question)
    rid = request_id_var.get()
    verdict = check_input(text, request_id=rid, principal=principal)
    if not verdict.allowed:
        return verdict.reply or _KID_FRIENDLY_ERROR, ""

    return None, text


async def _answer_with_guardrails_async(
    question: str,
    user_id: str,
    thread_id: str,
    *,
    principal: str = "-",
) -> str:
    """异步统一问答流程（一次性返回）。"""
    early, text = await _prepare_chat(question, user_id, principal=principal)
    if early is not None:
        return early

    if settings.llm_configured:
        try:
            from .resilience import ask_with_timeout_async

            raw = await ask_with_timeout_async(text, user_id=user_id, thread_id=thread_id)
            return sanitize_output(raw)
        except asyncio.TimeoutError:
            logger.warning("[req=%s] 在线问答超时", request_id_var.get())
            return _KID_FRIENDLY_ERROR
        except Exception as exc:  # noqa: BLE001 - 在线异常自动降级
            logger.warning("[req=%s] 在线问答失败，降级离线: %s", request_id_var.get(), exc)

    from .offline import offline_answer

    return sanitize_output(offline_answer(text))


async def _stream_answer_with_guardrails_async(
    question: str,
    user_id: str,
    thread_id: str,
    *,
    principal: str = "-",
):
    """流式问答：逐 chunk 产出；护栏拦截时一次性 yield early_reply。"""
    early, text = await _prepare_chat(question, user_id, principal=principal)
    if early is not None:
        yield early
        return

    if settings.llm_configured and settings.chat_stream_native:
        parts: list[str] = []
        try:
            from .resilience import stream_ask_async

            limit = settings.chat_timeout_seconds
            deadline = time.monotonic() + limit
            async for chunk in stream_ask_async(text, user_id=user_id, thread_id=thread_id):
                if time.monotonic() > deadline:
                    logger.warning("[req=%s] 流式问答超时", request_id_var.get())
                    tail = _KID_FRIENDLY_ERROR
                    if not parts:
                        yield tail
                    return
                parts.append(chunk)
                yield chunk
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("[req=%s] 流式在线失败，降级离线: %s", request_id_var.get(), exc)
            if parts:
                return

    from .offline import offline_answer

    yield sanitize_output(offline_answer(text))


@app.post("/api/chat")
async def chat(req: ChatRequest, principal: str = Depends(authenticate)):
    uid = derive_user_id(principal, req.user_id)
    tid = derive_thread_id(principal, req.thread_id)
    quota_resp = _enforce_llm_quota(principal)
    if quota_resp is not None:
        return quota_resp
    try:
        mode = "online" if settings.llm_configured else "offline"
        answer = await _answer_with_guardrails_async(req.question, uid, tid, principal=principal)
        persist_chat_log(
            user_id=uid,
            thread_id=tid,
            question=req.question,
            answer=answer,
            mode=mode,
            request_id=request_id_var.get(),
        )
        return {"answer": answer, "mode": mode}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": _kid_friendly_error(exc)})


def _sse_format(token: str) -> str:
    lines = token.split("\n")
    return "".join(f"data: {line}\n" for line in lines) + "\n"


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest, principal: str = Depends(authenticate)):
    uid = derive_user_id(principal, req.user_id)
    tid = derive_thread_id(principal, req.thread_id)
    quota_resp = _enforce_llm_quota(principal)
    if quota_resp is not None:
        return quota_resp

    async def event_generator():
        full_parts: list[str] = []
        mode = "online" if settings.llm_configured else "offline"
        try:
            if settings.llm_configured and settings.chat_stream_native:
                async for chunk in _stream_answer_with_guardrails_async(
                    req.question, uid, tid, principal=principal
                ):
                    full_parts.append(chunk)
                    yield _sse_format(chunk)
                    await asyncio.sleep(0)
            else:
                full = await _answer_with_guardrails_async(
                    req.question, uid, tid, principal=principal
                )
                full_parts.append(full)
                step = 12
                for i in range(0, len(full), step):
                    yield _sse_format(full[i : i + step])
                    await asyncio.sleep(0)
            answer = sanitize_output("".join(full_parts))
            persist_chat_log(
                user_id=uid,
                thread_id=tid,
                question=req.question,
                answer=answer,
                mode=mode,
                request_id=request_id_var.get(),
            )
        except Exception as exc:  # noqa: BLE001
            err = _kid_friendly_error(exc)
            yield _sse_format(err)
        yield "event: done\ndata: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/study-card")
async def study_card(req: QuestionRequest, principal: str = Depends(authenticate)):
    from .privacy import consent_denied_message, has_valid_consent
    from .services.text_utils import clean_text

    uid = derive_user_id(principal, "default")
    if not has_valid_consent(uid):
        return JSONResponse(status_code=403, content={"error": consent_denied_message()})

    text = clean_text(req.question)
    verdict = check_input(text, request_id=request_id_var.get(), principal=principal)
    if not verdict.allowed:
        return JSONResponse(status_code=200, content={"error": verdict.reply})
    if not settings.llm_configured:
        return JSONResponse(
            status_code=200,
            content={"error": "学习卡片需要在线大模型哦，请让大人配置后再试～🌈"},
        )
    quota_resp = _enforce_llm_quota(principal)
    if quota_resp is not None:
        return quota_resp
    try:
        from .agent import generate_study_card_async

        limit = settings.chat_timeout_seconds
        card = await asyncio.wait_for(generate_study_card_async(text), timeout=limit)
        return card.model_dump()
    except asyncio.TimeoutError:
        return JSONResponse(status_code=504, content={"error": _KID_FRIENDLY_ERROR})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": _kid_friendly_error(exc)})


# ==================== 出题 / 判分 ====================


@app.post("/api/quiz")
async def quiz(req: QuizRequest, principal: str = Depends(authenticate)):
    from .services import generate_quiz
    from .services.quiz_session import create_session

    try:
        q = await asyncio.to_thread(
            generate_quiz, req.grade, req.subject, req.count, req.seed
        )
        session_id = create_session(principal, q)
        return {
            "session_id": session_id,
            "public": q.public_dict(),
        }
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": _kid_friendly_error(exc)})


@app.post("/api/grade")
async def grade(req: GradeRequest, principal: str = Depends(authenticate)):
    from .domain import Grade, Question, Quiz, Subject
    from .services import grade_quiz
    from .services.quiz_session import consume_session

    try:
        quiz_obj = consume_session(req.session_id, principal)
        if quiz_obj is None:
            if (
                not settings.is_production
                and req.questions
                and req.grade
                and req.subject
            ):
                quiz_obj = Quiz(
                    grade=Grade.parse(req.grade),
                    subject=Subject.parse(req.subject),
                    questions=[Question(**q) for q in req.questions],
                )
            else:
                return JSONResponse(
                    status_code=400,
                    content={"error": "练习会话无效或已过期，请重新出题"},
                )

        uid = derive_user_id(principal, "quiz")
        result = await asyncio.to_thread(grade_quiz, quiz_obj, req.answers)
        persist_quiz_record(
            user_id=uid,
            grade=quiz_obj.grade.value,
            subject=quiz_obj.subject.value,
            total=result.total,
            correct=result.correct,
            score=result.score,
            detail_json={"items": [i.model_dump() for i in result.items]},
        )
        return result.model_dump()
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": _kid_friendly_error(exc)})


# ==================== 长期记忆（合规：查看 / 清除）====================


@app.get("/api/memory")
def memory_view(
    sub: str = Query(default="default"),
    principal: str = Depends(authenticate),
):
    from .memory_admin import list_memories

    uid = derive_user_id(principal, sub)
    try:
        data = list_memories(uid)
        memory_access(
            "view",
            user_id=uid,
            principal=principal,
            request_id=request_id_var.get(),
            detail=f"facts={len(data.get('facts', []))}",
        )
        return data
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": _kid_friendly_error(exc)})


@app.delete("/api/memory")
def memory_clear(
    sub: str = Query(default="default"),
    principal: str = Depends(authenticate),
):
    from .memory_admin import clear_memories

    uid = derive_user_id(principal, sub)
    try:
        removed = clear_memories(uid)
        memory_access(
            "clear",
            user_id=uid,
            principal=principal,
            request_id=request_id_var.get(),
            detail=f"removed={removed}",
        )
        return {"status": "ok", "removed": removed}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": _kid_friendly_error(exc)})


@app.get("/api/privacy/export")
def privacy_export(
    sub: str = Query(default="default"),
    principal: str = Depends(authenticate),
):
    """合规：导出某用户长期记忆 + 近期对话/练习记录（家长可请求）。"""
    from .memory_admin import list_memories

    uid = derive_user_id(principal, sub)
    try:
        export: dict = {
            "user_id": uid,
            "memory": list_memories(uid),
            "chat_logs": [],
            "quiz_records": [],
        }
        if settings.mysql_configured and settings.mysql_audit_enabled:
            try:
                from .mysql import ChatLogRepository, QuizRecordRepository

                export["chat_logs"] = ChatLogRepository().list_recent(uid, limit=50)
                export["quiz_records"] = QuizRecordRepository().list_by_user(uid, limit=50)
            except Exception as exc:  # noqa: BLE001
                export["mysql_error"] = str(exc)
        memory_access(
            "export",
            user_id=uid,
            principal=principal,
            request_id=request_id_var.get(),
            detail="privacy_export",
        )
        return export
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": _kid_friendly_error(exc)})


@app.get("/api/privacy/policy")
def privacy_policy():
    """隐私政策与家长权利说明（公开）。"""
    from .privacy import get_policy

    return get_policy()


@app.get("/api/privacy/consent")
def privacy_consent_status(
    sub: str = Query(default="default"),
    principal: str = Depends(authenticate),
):
    from .privacy import get_consent, has_valid_consent

    uid = derive_user_id(principal, sub)
    row = get_consent(uid)
    return {
        "user_id": uid,
        "required": settings.require_parent_consent,
        "valid": has_valid_consent(uid),
        "consent": row,
        "policy_version": settings.consent_policy_version,
    }


@app.post("/api/privacy/consent")
def privacy_consent_record(
    req: ConsentRequest,
    request: Request,
    principal: str = Depends(authenticate),
):
    from .privacy import record_consent

    uid = derive_user_id(principal, req.sub)
    ip = client_id_from_request(request) if request else None
    row = record_consent(
        uid,
        parent_name=req.parent_name,
        parent_email=req.parent_email,
        ip_address=ip,
    )
    memory_access(
        "consent",
        user_id=uid,
        principal=principal,
        request_id=request_id_var.get(),
        detail=f"version={settings.consent_policy_version}",
    )
    return {"status": "ok", "consent": row}


@app.delete("/api/privacy/account")
def privacy_account_delete(
    sub: str = Query(default="default"),
    principal: str = Depends(authenticate),
):
    from .privacy import delete_all_user_data

    uid = derive_user_id(principal, sub)
    result = delete_all_user_data(uid)
    memory_access(
        "delete_account",
        user_id=uid,
        principal=principal,
        request_id=request_id_var.get(),
        detail="privacy_account_delete",
    )
    return {"status": "ok", **result}


@app.post("/api/privacy/retention/sweep")
def privacy_retention_sweep(request: Request):
    """Cron/运维：清理超期审计数据。需 ``KIDS_RETENTION_SWEEP_TOKEN``。"""
    token = settings.retention_sweep_token
    if token:
        presented = request.headers.get("X-Retention-Token") or request.headers.get(
            "Authorization", ""
        ).removeprefix("Bearer ").strip()
        if not compare_secret(presented, token):
            return PlainTextResponse("forbidden", status_code=403)
    elif settings.is_production:
        return PlainTextResponse("forbidden", status_code=403)

    from .privacy import sweep_expired_audit_data

    return sweep_expired_audit_data()


@app.post("/api/ingest")
async def ingest(
    _: None = Depends(verify_ingest_token),
    principal: str = Depends(authenticate),
):
    try:
        from .knowledge import build_index

        count = await asyncio.to_thread(build_index)
        return {"status": "ok", "index_count": count}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


# ==================== 内嵌 Web UI ====================

INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>小博士 - 小学生 AI 学习伙伴</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
         background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); height: 100vh;
         display: flex; align-items: center; justify-content: center; }
  .app { width: 100%; max-width: 720px; height: 92vh; background: #fff; border-radius: 24px;
         box-shadow: 0 20px 60px rgba(0,0,0,.15); display: flex; flex-direction: column; overflow: hidden; }
  .header { background: linear-gradient(135deg, #6a8dff, #9d7bff); color: #fff; padding: 18px 24px; }
  .header h1 { margin: 0; font-size: 22px; }
  .header p { margin: 6px 0 0; font-size: 13px; opacity: .9; }
  .chat { flex: 1; padding: 20px; overflow-y: auto; background: #f7f9ff; }
  .msg { margin: 12px 0; display: flex; }
  .msg.user { justify-content: flex-end; }
  .bubble { max-width: 80%; padding: 12px 16px; border-radius: 16px; line-height: 1.6;
            white-space: pre-wrap; word-break: break-word; font-size: 15px; }
  .user .bubble { background: #6a8dff; color: #fff; border-bottom-right-radius: 4px; }
  .bot .bubble { background: #fff; color: #333; border: 1px solid #e6e8f0; border-bottom-left-radius: 4px; }
  .footer { padding: 14px; border-top: 1px solid #eef0f6; background: #fff; }
  .row { display: flex; gap: 10px; }
  #q { flex: 1; padding: 12px 16px; border: 1px solid #d6dbe8; border-radius: 14px; font-size: 15px; outline: none; }
  #q:focus { border-color: #6a8dff; }
  button { padding: 12px 22px; border: none; border-radius: 14px; background: #6a8dff; color: #fff;
           font-size: 15px; cursor: pointer; }
  button:disabled { opacity: .5; cursor: not-allowed; }
  .hint { font-size: 12px; color: #99a; margin-top: 8px; }
</style>
</head>
<body>
  <div class="app">
    <div class="header">
      <h1>小博士 AI 学习伙伴</h1>
      <p>语文 · 数学 · 科学 · 安全 · 健康 —— 有问题就问我吧！</p>
    </div>
    <div class="chat" id="chat">
      <div class="msg bot"><div class="bubble">你好呀！我是小博士，可以陪你一起学习。试着问我："太阳系有几大行星？""过马路要注意什么？"吧！</div></div>
    </div>
    <div class="footer">
      <div class="row">
        <input id="q" placeholder="在这里输入你的问题..." autocomplete="off" />
        <button id="send" onclick="send()">发送</button>
      </div>
      <div class="hint">小提示：我会记住你的名字和爱好，下次还认得你哦～</div>
    </div>
  </div>
<script>
  const chat = document.getElementById('chat');
  const qInput = document.getElementById('q');
  const sendBtn = document.getElementById('send');
  const userId = 'web-' + Math.random().toString(36).slice(2, 8);
  const threadId = 'web-thread-' + Math.random().toString(36).slice(2, 8);

  function addBubble(text, who) {
    const msg = document.createElement('div');
    msg.className = 'msg ' + who;
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = text;
    msg.appendChild(bubble);
    chat.appendChild(msg);
    chat.scrollTop = chat.scrollHeight;
    return bubble;
  }

  async function send() {
    const question = qInput.value.trim();
    if (!question) return;
    qInput.value = '';
    sendBtn.disabled = true;
    addBubble(question, 'user');
    const botBubble = addBubble('', 'bot');

    try {
      const resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, user_id: userId, thread_id: threadId })
      });
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split('\\n\\n');
        buffer = frames.pop();
        for (const frame of frames) {
          if (frame.startsWith('event: done')) continue;
          const dataLines = frame.split('\\n')
            .filter(l => l.startsWith('data: '))
            .map(l => l.slice(6));
          const text = dataLines.join('\\n');
          if (text && text !== '[DONE]') {
            botBubble.textContent += text;
            chat.scrollTop = chat.scrollHeight;
          }
        }
      }
    } catch (e) {
      botBubble.textContent = '哎呀，连接出错了：' + e;
    } finally {
      sendBtn.disabled = false;
      qInput.focus();
    }
  }

  qInput.addEventListener('keydown', e => { if (e.key === 'Enter') send(); });
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    if not settings.embedded_ui_allowed:
        return PlainTextResponse("Not Found", status_code=404)
    return INDEX_HTML
