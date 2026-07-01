"""学习域 + 家长端 + KP 目录 REST API。"""



from __future__ import annotations



from fastapi import APIRouter, Depends, HTTPException, Query

from fastapi.responses import Response



from ..config import settings

from ..security import authenticate, derive_user_id

from . import (

    attempt_service,

    dimension_service,

    evolution_service,

    gap_service,

    kp_catalog,

    kp_review,

    photo_service,

    plan_service,

    proactive_service,

    push_queue,

    textbook_ingest,

    vision_service,

    wiki_service,

)

from .context_service import build_context, build_progress_view, format_context_for_prompt

from .question_bank import question_public, suggest_questions

from .schemas import (

    AttemptRequest,

    FreeformAttemptRequest,

    GapOverrideRequest,

    KpReviewSubmitRequest,

    OnboardingRequest,

    PhotoClassifyRequest,

    PushQueueRebuildRequest,

    ResolveInboxRequest,

    SuggestQuestionsRequest,

    TextbookIngestRequest,

    TtsRequest,

    VisionChatRequest,

    VisionUnderstandRequest,

    WikiUpsertRequest,

)



learning_router = APIRouter(prefix="/api/learning", tags=["learning"])

parent_router = APIRouter(prefix="/api/parent", tags=["parent"])

kp_router = APIRouter(prefix="/api/kp", tags=["kp"])

review_router = APIRouter(prefix="/api/kp-review", tags=["kp-review"])





def _student_id(principal: str, requested: str | None) -> str:

    if requested:

        return derive_user_id(principal, requested)

    if principal.startswith("jwt:"):

        return derive_user_id(principal, principal[4:])

    return derive_user_id(principal, "default-student")





@learning_router.get("/context")

def learning_context(

    user_id: str | None = Query(None),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    return build_context(sid).model_dump()





@learning_router.get("/context/prompt")

def learning_context_prompt(

    user_id: str | None = Query(None),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    return {"text": format_context_for_prompt(sid)}





@learning_router.post("/onboarding")

def onboarding(

    req: OnboardingRequest,

    user_id: str | None = Query(None),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    try:

        profile = attempt_service.onboard(

            sid, req.grade, req.subject, req.unit_id, req.self_assessment

        )

    except kp_catalog.GradeBoundaryError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"status": "ok", "profile": profile.model_dump()}





@learning_router.get("/profile")

def get_profile(

    user_id: str | None = Query(None),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    p = attempt_service.get_profile(sid)

    return {"profile": p.model_dump() if p else None}





@learning_router.get("/gaps")

def list_gaps(

    user_id: str | None = Query(None),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    return {"gaps": [g.model_dump() for g in gap_service.list_gaps(sid)]}





@learning_router.post("/attempts")

def submit_attempt(

    req: AttemptRequest,

    user_id: str | None = Query(None),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    if not req.question_id:

        raise HTTPException(status_code=400, detail="question_id 必填")

    try:

        attempt = attempt_service.submit_bank_attempt(sid, req.question_id, req.answer)

    except KeyError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except kp_catalog.GradeBoundaryError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    proactive = proactive_service.after_attempt_message(sid, attempt)

    return {"attempt": attempt.model_dump(), "proactive_message": proactive}





@learning_router.post("/attempts/freeform")

def submit_freeform(

    req: FreeformAttemptRequest,

    user_id: str | None = Query(None),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    attempt = attempt_service.submit_freeform(sid, req)

    proactive = proactive_service.after_attempt_message(sid, attempt)

    return {"attempt": attempt.model_dump(), "proactive_message": proactive}





@learning_router.get("/attempts")

def list_attempts(

    user_id: str | None = Query(None),

    limit: int = Query(20, ge=1, le=100),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    return {"attempts": [a.model_dump() for a in attempt_service.list_attempts(sid, limit)]}





@learning_router.post("/questions/suggest")

def suggest(

    req: SuggestQuestionsRequest,

    user_id: str | None = Query(None),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    profile = attempt_service.get_profile(sid)

    grade = profile.grade_level if profile else 2

    kp_ids = [req.knowledge_point_id] if req.knowledge_point_id else None

    if req.weak_only and not kp_ids:

        kp_ids = gap_service.weak_kp_ids(sid) or None

    qs = suggest_questions(kp_ids=kp_ids, grade=grade, count=req.count)

    return {"questions": [q.model_dump() for q in qs]}





@learning_router.get("/questions/{question_id}")

def get_question(question_id: str, principal: str = Depends(authenticate)):

    q = question_public(question_id)

    if not q:

        raise HTTPException(status_code=404, detail="题目不存在")

    return q.model_dump()





@learning_router.post("/plan")

def create_plan(

    user_id: str | None = Query(None),

    minutes: int = Query(20, ge=10, le=60),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    plan = plan_service.generate_plan(sid, minutes)

    return {"plan": plan.model_dump()}





@learning_router.get("/progress")

def progress_view(

    user_id: str | None = Query(None),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    return build_progress_view(sid).model_dump()





@learning_router.get("/dimensions")

def dimension_scores(

    user_id: str | None = Query(None),

    days: int = Query(7, ge=1, le=30),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    return {

        "scores": dimension_service.compute_dimension_scores(sid, days),

        "behavior_tags": dimension_service.behavior_tags(sid, days),

    }





@learning_router.get("/proactive")

def proactive_messages(

    user_id: str | None = Query(None),

    limit: int = Query(5, ge=1, le=20),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    reminder = proactive_service.check_recurrence_reminder(sid)

    return {

        "messages": proactive_service.list_proactive_messages(sid, limit),

        "recurrence_reminder": reminder,

    }





@learning_router.get("/remediation")

def remediation_skills(

    user_id: str | None = Query(None),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    return {"skills": evolution_service.list_skills(sid)}





@learning_router.post("/photo/classify")

def classify_photo(

    req: PhotoClassifyRequest,

    user_id: str | None = Query(None),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    triage, result = photo_service.classify_photo(sid, req)

    payload: dict = {"triage": triage}

    if result is not None:

        if hasattr(result, "model_dump"):

            payload["result"] = result.model_dump()

    return payload





@learning_router.get("/photo/inbox")

def photo_inbox(

    user_id: str | None = Query(None),

    status: str = Query("pending"),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    items = photo_service.list_inbox(student_id=sid, status=status)

    return {"items": [i.model_dump() for i in items]}





@learning_router.post("/photo/inbox/{inbox_id}/resolve")

def resolve_inbox(

    inbox_id: str,

    req: ResolveInboxRequest,

    principal: str = Depends(authenticate),

):

    try:

        item = photo_service.resolve_inbox(inbox_id, req.action, req.knowledge_point_id)

    except KeyError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"item": item.model_dump()}





@learning_router.post("/vision/understand")

def vision_understand(

    req: VisionUnderstandRequest,

    user_id: str | None = Query(None),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    resp = vision_service.understand_text(sid, req.text, mode=req.mode)

    return resp.model_dump()





@learning_router.post("/vision/chat")

async def vision_chat(

    req: VisionChatRequest,

    user_id: str | None = Query(None),

    principal: str = Depends(authenticate),

):

    """P7：Vision 理解 + 可选 Agent 追问（不直连 classify）。"""

    sid = _student_id(principal, user_id)

    vision = vision_service.understand_text(sid, req.text, mode=req.mode)

    answer = None

    if req.follow_up:

        from ..resilience import ask_with_timeout_async



        ctx = vision_service.format_vision_for_prompt(vision.vision_id)

        question = f"{ctx}\n\n用户问题：{req.follow_up}" if ctx else req.follow_up

        try:

            answer = await ask_with_timeout_async(

                question, sid, sid, timeout=settings.chat_timeout_seconds

            )

        except Exception:

            answer = None

    return {"vision": vision.model_dump(), "answer": answer}





@learning_router.get("/push-queue")

def get_push_queue(

    user_id: str | None = Query(None),

    n: int = Query(3, ge=1, le=10),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    return {"questions": [q.model_dump() for q in push_queue.peek(sid, n)]}





@learning_router.post("/push-queue/rebuild")

def rebuild_push_queue(

    req: PushQueueRebuildRequest,

    user_id: str | None = Query(None),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    profile = attempt_service.get_profile(sid)

    grade = profile.grade_level if profile else 2

    items = push_queue.rebuild_queue(sid, grade=grade, count=req.count)

    return {"items": items}





@learning_router.post("/push-queue/pop")

def pop_push_queue(

    user_id: str | None = Query(None),

    principal: str = Depends(authenticate),

):

    sid = _student_id(principal, user_id)

    q = push_queue.pop_next(sid)

    return {"question": q.model_dump() if q else None}





@learning_router.get("/wiki/search")

def wiki_search(

    q: str = Query(..., min_length=1),

    grade: int | None = Query(None),

    principal: str = Depends(authenticate),

):

    return {"hits": wiki_service.search_wiki(q, grade=grade)}





@learning_router.get("/wiki/kp/{kp_id}")

def wiki_kp(kp_id: str, principal: str = Depends(authenticate)):

    return {"content": wiki_service.explain_kp_wiki(kp_id)}





@learning_router.put("/wiki/kp/{kp_id}")

def wiki_upsert(

    kp_id: str,

    req: WikiUpsertRequest,

    principal: str = Depends(authenticate),

):

    wiki_service.upsert_wiki(kp_id, req.content)

    return {"status": "ok", "kp_id": kp_id}





@learning_router.post("/tts")

async def text_to_speech(req: TtsRequest, principal: str = Depends(authenticate)):

    try:

        import edge_tts  # type: ignore



        communicate = edge_tts.Communicate(req.text[:500], req.voice)

        audio = b""

        async for chunk in communicate.stream():

            if chunk["type"] == "audio":

                audio += chunk["data"]

        return Response(content=audio, media_type="audio/mpeg")

    except ImportError:

        return {"fallback": True, "message": "请使用浏览器朗读", "text": req.text}

    except Exception as exc:

        return {"fallback": True, "message": str(exc), "text": req.text}





# ---------- 家长端 ----------



@parent_router.get("/students")

def parent_students(principal: str = Depends(authenticate)):

    sid = derive_user_id(principal, None)

    profile = attempt_service.get_profile(sid)

    return {

        "students": [

            {

                "id": sid,

                "display_name": profile.grade if profile else "小朋友",

                "grade": profile.grade if profile else "未设置",

            }

        ]

    }





@parent_router.get("/students/{student_id}/profile")

def parent_learning_profile(student_id: str, principal: str = Depends(authenticate)):

    _student_id(principal, student_id)

    ctx = build_context(student_id)

    inbox = photo_service.list_inbox(student_id=student_id)

    dims = dimension_service.compute_dimension_scores(student_id)

    return {

        "context": ctx.model_dump(),

        "inbox": [i.model_dump() for i in inbox],

        "dimension_scores": dims,

        "behavior_tags": dimension_service.behavior_tags(student_id),

    }





@parent_router.get("/students/{student_id}/report")

def parent_report(

    student_id: str,

    days: int = Query(7, ge=1, le=30),

    principal: str = Depends(authenticate),

):

    _student_id(principal, student_id)

    report = plan_service.generate_parent_report(student_id, days)

    return report.model_dump()





@parent_router.post("/students/{student_id}/report/generate")

def generate_report(student_id: str, principal: str = Depends(authenticate)):

    _student_id(principal, student_id)

    report = plan_service.generate_parent_report(student_id, 7)

    return report.model_dump()





@parent_router.patch("/students/{student_id}/gaps/{kp_id}")

def override_gap(

    student_id: str,

    kp_id: str,

    req: GapOverrideRequest,

    principal: str = Depends(authenticate),

):

    _student_id(principal, student_id)

    gap = gap_service.override_gap(student_id, kp_id, req.status, req.note)

    return {"gap": gap.model_dump()}





# ---------- KP 目录 ----------



@kp_router.get("/catalog")

def kp_catalog_list(

    grade: int | None = Query(None),

    subject: str | None = Query(None),

    principal: str = Depends(authenticate),

):

    units = kp_catalog.list_units(grade_level=grade, subject=subject)

    return {"units": [u.model_dump() for u in units]}





@kp_router.get("/units/{unit_id}")

def kp_unit(unit_id: str, principal: str = Depends(authenticate)):

    try:

        unit = kp_catalog.get_unit(unit_id)

    except KeyError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return unit.model_dump()





@kp_router.post("/review/reload")

def reload_kp_catalog(principal: str = Depends(authenticate)):

    kp_catalog.reload_catalog()

    return {"status": "ok", "count": len(kp_catalog.load_catalog())}





# ---------- KP 审核 ----------



@review_router.get("/jobs")

def list_review_jobs(

    status: str | None = Query(None),

    principal: str = Depends(authenticate),

):

    return {"jobs": kp_review.list_jobs(status)}





@review_router.get("/jobs/{job_id}")

def get_review_job(job_id: str, principal: str = Depends(authenticate)):

    job = kp_review.get_job(job_id)

    if not job:

        raise HTTPException(status_code=404, detail="任务不存在")

    return job





@review_router.post("/submit")

def submit_review(req: KpReviewSubmitRequest, principal: str = Depends(authenticate)):

    job = kp_review.submit_kp_text(req.content, req.filename)

    return job





@review_router.post("/jobs/{job_id}/approve")

def approve_review_job(job_id: str, principal: str = Depends(authenticate)):

    try:

        job = kp_review.approve_job(job_id)

    except KeyError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return job



# ---------- 教材 Ingest（P0 stub） ----------

@review_router.get("/ingest/jobs")

def list_ingest_jobs(

    status: str | None = Query(None),

    principal: str = Depends(authenticate),

):

    return {"jobs": textbook_ingest.list_jobs(status)}



@review_router.post("/ingest/submit")

def submit_ingest(req: TextbookIngestRequest, principal: str = Depends(authenticate)):

    return textbook_ingest.submit_text(

        req.content,

        source_type=req.source_type,

        grade_level=req.grade_level,

        subject=req.subject,

        unit_id_hint=req.unit_id_hint,

    )



@review_router.post("/ingest/jobs/{job_id}/promote")

def promote_ingest(job_id: str, principal: str = Depends(authenticate)):

    try:

        return textbook_ingest.promote_to_kp_review(job_id)

    except KeyError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc


