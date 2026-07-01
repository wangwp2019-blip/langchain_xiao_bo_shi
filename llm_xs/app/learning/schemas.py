"""学习域 Pydantic 模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

GapStatus = Literal["weak", "learning", "mastered", "unknown"]
AttemptSource = Literal["bank", "freeform", "photo", "manual"]
PhotoStatus = Literal["pending", "resolved", "ignored"]
PhotoTriage = Literal["auto", "inbox", "explain_only"]


class KnowledgePoint(BaseModel):
    knowledge_point_id: str
    title: str
    description: str = ""


class UnitCatalogEntry(BaseModel):
    unit_id: str
    grade: int
    subject: str
    unit_title: str
    textbook_ref: str = ""
    knowledge_points: list[KnowledgePoint] = Field(default_factory=list)


class OnboardingRequest(BaseModel):
    grade: str = Field(..., description="如 二年级")
    subject: str = Field(default="数学")
    unit_id: str | None = None
    self_assessment: str | None = Field(None, description="自评：很好/一般/需加强")


class OnboardingProfile(BaseModel):
    student_id: str
    grade: str
    grade_level: int
    subject: str
    unit_id: str | None = None
    self_assessment: str | None = None
    onboarded_at: str


class AttemptRequest(BaseModel):
    question_id: str | None = None
    answer: str
    session_id: str | None = None


class FreeformAttemptRequest(BaseModel):
    prompt: str
    student_answer: str
    subject: str = "数学"


class AttemptRecord(BaseModel):
    attempt_id: str
    student_id: str
    question_id: str | None = None
    knowledge_point_id: str
    is_correct: bool
    error_code: str | None = None
    source: AttemptSource = "bank"
    prompt: str = ""
    student_answer: str = ""
    feedback: str = ""
    created_at: str


class GapEntry(BaseModel):
    knowledge_point_id: str
    title: str
    status: GapStatus = "unknown"
    correct_streak: int = 0
    attempt_count: int = 0
    last_attempt_id: str | None = None
    provenance: str = "attempt"
    updated_at: str = ""


class StudentContext(BaseModel):
    student_id: str
    profile: OnboardingProfile | None = None
    top_gaps: list[GapEntry] = Field(default_factory=list)
    mastered_count: int = 0
    total_kp_tracked: int = 0
    recent_attempts: list[AttemptRecord] = Field(default_factory=list)
    pending_photos: int = 0


class QuestionPublic(BaseModel):
    question_id: str
    prompt: str
    knowledge_point_id: str
    unit_id: str
    grade: int
    subject: str


class SuggestQuestionsRequest(BaseModel):
    knowledge_point_id: str | None = None
    weak_only: bool = True
    count: int = Field(default=3, ge=1, le=10)


class PhotoClassifyRequest(BaseModel):
    text: str = Field(..., description="OCR 文本或 Vision 描述")
    subject: str = "数学"
    image_note: str = ""


class PhotoInboxItem(BaseModel):
    inbox_id: str
    student_id: str
    text: str
    suggested_kp_id: str | None = None
    suggested_kp_title: str = ""
    confidence: float = 0.0
    triage: PhotoTriage = "inbox"
    status: PhotoStatus = "pending"
    created_at: str
    resolved_kp_id: str | None = None


class ResolveInboxRequest(BaseModel):
    action: Literal["attach", "ignore"]
    knowledge_point_id: str | None = None


class StudyPlanStep(BaseModel):
    step: int
    title: str
    action: str
    knowledge_point_id: str | None = None
    duration_min: int = 5


class StudyPlan(BaseModel):
    plan_id: str
    student_id: str
    title: str
    steps: list[StudyPlanStep]
    total_minutes: int = 20
    created_at: str


class ProgressView(BaseModel):
    """T4 鼓励性进度视图（不展示薄弱清单）。"""
    student_id: str
    encouragement: str
    mastered_titles: list[str] = Field(default_factory=list)
    learning_titles: list[str] = Field(default_factory=list)
    streak_days: int = 0
    total_attempts: int = 0
    recent_wins: list[str] = Field(default_factory=list)


class ParentReport(BaseModel):
    student_id: str
    period_days: int = 7
    summary: str
    attempts_total: int = 0
    correct_rate: float | None = None
    mastered_count: int = 0
    weak_count: int = 0
    knowledge_section: list[dict[str, Any]] = Field(default_factory=list)
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    habit_notes: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: str


class GapOverrideRequest(BaseModel):
    status: GapStatus
    note: str = ""


class VisionUnderstandRequest(BaseModel):
    text: str = Field(..., description="图片 OCR 或描述文本")
    mode: Literal["homework", "graded"] = "homework"


class VisionItem(BaseModel):
    index: int
    prompt: str
    student_answer: str | None = None
    is_correct: bool | None = None
    knowledge_point_id: str | None = None


class VisionUnderstandResponse(BaseModel):
    vision_id: str
    summary: str
    items: list[VisionItem] = Field(default_factory=list)
    triage: PhotoTriage = "auto"


class TtsRequest(BaseModel):
    text: str = Field(..., max_length=2000)
    voice: str = "zh-CN-XiaoxiaoNeural"


class KpReviewSubmitRequest(BaseModel):
    content: str = Field(..., description="kp.md 全文")
    filename: str = "upload.kp.md"


class WikiUpsertRequest(BaseModel):
    content: str


class TextbookIngestRequest(BaseModel):
    content: str = Field(..., description="教材文本（PDF 抽取/OCR/粘贴）")
    source_type: str = Field(default="document")
    grade_level: int = Field(default=2, ge=1, le=6)
    subject: str | None = None
    unit_id_hint: str | None = None


class PushQueueRebuildRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=20)


class VisionChatRequest(BaseModel):
    text: str
    mode: Literal["homework", "graded"] = "homework"
    follow_up: str | None = Field(None, description="Vision 后追问，走 Agent 编排")
