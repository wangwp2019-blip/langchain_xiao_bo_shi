import type {
  AttemptRecord,
  GapEntry,
  KpReviewJob,
  LearningQuestion,
  OnboardingProfile,
  ParentReport,
  PhotoInboxItem,
  ProgressView,
  StudyCard,
  StudyPlan,
  UnitCatalogEntry,
  VisionUnderstandResponse,
} from "./learning-types";
import { getToken } from "./api";

function authHeaders(): HeadersInit {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

async function getJSON<T>(path: string): Promise<T> {
  const resp = await fetch(path, { headers: authHeaders() });
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json() as Promise<T>;
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(path, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json() as Promise<T>;
}

async function patchJSON<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(path, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json() as Promise<T>;
}

export async function fetchProfile(studentId: string): Promise<OnboardingProfile | null> {
  const data = await getJSON<{ profile: OnboardingProfile | null }>(
    `/api/learning/profile?user_id=${encodeURIComponent(studentId)}`,
  );
  return data.profile;
}

export async function submitOnboarding(
  studentId: string,
  grade: string,
  subject: string,
  unitId?: string,
  selfAssessment?: string,
): Promise<OnboardingProfile> {
  const data = await postJSON<{ profile: OnboardingProfile }>(
    `/api/learning/onboarding?user_id=${encodeURIComponent(studentId)}`,
    { grade, subject, unit_id: unitId, self_assessment: selfAssessment },
  );
  return data.profile;
}

export async function fetchGaps(studentId: string): Promise<GapEntry[]> {
  const data = await getJSON<{ gaps: GapEntry[] }>(
    `/api/learning/gaps?user_id=${encodeURIComponent(studentId)}`,
  );
  return data.gaps;
}

export async function suggestLearningQuestions(
  studentId: string,
  count = 3,
): Promise<LearningQuestion[]> {
  const data = await postJSON<{ questions: LearningQuestion[] }>(
    `/api/learning/questions/suggest?user_id=${encodeURIComponent(studentId)}`,
    { count, weak_only: true },
  );
  return data.questions;
}

export async function submitLearningAttempt(
  studentId: string,
  questionId: string,
  answer: string,
): Promise<AttemptRecord> {
  const data = await postJSON<{ attempt: AttemptRecord }>(
    `/api/learning/attempts?user_id=${encodeURIComponent(studentId)}`,
    { question_id: questionId, answer },
  );
  return data.attempt;
}

export async function fetchProgress(studentId: string): Promise<ProgressView> {
  return getJSON<ProgressView>(
    `/api/learning/progress?user_id=${encodeURIComponent(studentId)}`,
  );
}

export async function createStudyPlan(studentId: string): Promise<StudyPlan> {
  const data = await postJSON<{ plan: StudyPlan }>(
    `/api/learning/plan?user_id=${encodeURIComponent(studentId)}`,
    {},
  );
  return data.plan;
}

export async function classifyPhoto(
  studentId: string,
  text: string,
): Promise<{ triage: string; result?: unknown }> {
  return postJSON(`/api/learning/photo/classify?user_id=${encodeURIComponent(studentId)}`, {
    text,
    subject: "数学",
  });
}

export async function visionUnderstand(
  studentId: string,
  text: string,
  mode: "homework" | "graded" = "homework",
): Promise<VisionUnderstandResponse> {
  return postJSON(
    `/api/learning/vision/understand?user_id=${encodeURIComponent(studentId)}`,
    { text, mode },
  );
}

export async function fetchKpReviewJobs(): Promise<KpReviewJob[]> {
  const data = await getJSON<{ jobs: KpReviewJob[] }>("/api/kp-review/jobs");
  return data.jobs;
}

export async function submitKpReview(content: string, filename = "upload.kp.md"): Promise<KpReviewJob> {
  return postJSON("/api/kp-review/submit", { content, filename });
}

export async function approveKpReviewJob(jobId: string): Promise<KpReviewJob> {
  return postJSON(`/api/kp-review/jobs/${encodeURIComponent(jobId)}/approve`, {});
}

export interface TextbookIngestJob {
  job_id: string;
  source_type: string;
  status: string;
  grade_level: number;
  subject?: string | null;
  extracted_text_preview: string;
  kp_candidates: unknown[];
  created_at: string;
}

export async function fetchIngestJobs(): Promise<TextbookIngestJob[]> {
  const data = await getJSON<{ jobs: TextbookIngestJob[] }>("/api/kp-review/ingest/jobs");
  return data.jobs;
}

export async function submitIngest(content: string, opts?: {
  source_type?: string; grade_level?: number; subject?: string;
}): Promise<TextbookIngestJob> {
  return postJSON("/api/kp-review/ingest/submit", {
    content,
    source_type: opts?.source_type || "document",
    grade_level: opts?.grade_level || 2,
    subject: opts?.subject,
  });
}

export async function promoteIngest(jobId: string): Promise<TextbookIngestJob> {
  return postJSON(`/api/kp-review/ingest/jobs/${encodeURIComponent(jobId)}/promote`, {});
}

export async function fetchDimensions(studentId: string): Promise<{
  scores: Record<string, number>;
  behavior_tags: string[];
}> {
  return getJSON(`/api/learning/dimensions?user_id=${encodeURIComponent(studentId)}`);
}

export async function fetchProactive(studentId: string, limit = 5): Promise<{
  messages: { message: string; kind: string; created_at: string }[];
  recurrence_reminder: string | null;
}> {
  return getJSON(
    `/api/learning/proactive?user_id=${encodeURIComponent(studentId)}&limit=${limit}`,
  );
}

export async function fetchPushQueue(studentId: string, n = 3): Promise<LearningQuestion[]> {
  const data = await getJSON<{ questions: LearningQuestion[] }>(
    `/api/learning/push-queue?user_id=${encodeURIComponent(studentId)}&n=${n}`,
  );
  return data.questions;
}

export async function rebuildPushQueue(studentId: string, count = 5): Promise<{ items: unknown[] }> {
  return postJSON(
    `/api/learning/push-queue/rebuild?user_id=${encodeURIComponent(studentId)}`,
    { count },
  );
}

export async function popPushQueue(studentId: string): Promise<LearningQuestion | null> {
  const data = await postJSON<{ question: LearningQuestion | null }>(
    `/api/learning/push-queue/pop?user_id=${encodeURIComponent(studentId)}`,
    {},
  );
  return data.question;
}

export async function fetchRemediation(studentId: string): Promise<{
  skills: { kp_id: string; title: string; strategy: string; success_count: number; promoted: boolean }[];
}> {
  return getJSON(`/api/learning/remediation?user_id=${encodeURIComponent(studentId)}`);
}

export async function searchWiki(q: string, grade?: number): Promise<{
  hits: { unit_id: string; knowledge_point_id: string; title: string; snippet: string }[];
}> {
  const g = grade ? `&grade=${grade}` : "";
  return getJSON(`/api/learning/wiki/search?q=${encodeURIComponent(q)}${g}`);
}

export async function fetchKpWiki(kpId: string): Promise<{ content: string }> {
  return getJSON(`/api/learning/wiki/kp/${encodeURIComponent(kpId)}`);
}

export async function fetchParentProfile(studentId: string): Promise<{
  context: unknown;
  inbox: PhotoInboxItem[];
}> {
  return getJSON(`/api/parent/students/${encodeURIComponent(studentId)}/profile`);
}

export async function fetchParentReport(studentId: string): Promise<ParentReport> {
  return getJSON(`/api/parent/students/${encodeURIComponent(studentId)}/report`);
}

export async function resolveInbox(
  inboxId: string,
  action: "attach" | "ignore",
  kpId?: string,
): Promise<PhotoInboxItem> {
  const data = await postJSON<{ item: PhotoInboxItem }>(
    `/api/learning/photo/inbox/${encodeURIComponent(inboxId)}/resolve`,
    { action, knowledge_point_id: kpId },
  );
  return data.item;
}

export async function overrideGap(
  studentId: string,
  kpId: string,
  status: GapEntry["status"],
  note?: string,
): Promise<GapEntry> {
  const data = await patchJSON<{ gap: GapEntry }>(
    `/api/parent/students/${encodeURIComponent(studentId)}/gaps/${encodeURIComponent(kpId)}`,
    { status, note },
  );
  return data.gap;
}

export async function fetchKpCatalog(grade?: number): Promise<UnitCatalogEntry[]> {
  const q = grade ? `?grade=${grade}` : "";
  const data = await getJSON<{ units: UnitCatalogEntry[] }>(`/api/kp/catalog${q}`);
  return data.units;
}

export async function generateStudyCard(question: string): Promise<StudyCard> {
  return postJSON<StudyCard>("/api/study-card", { question });
}

export function speakText(text: string, lang: string): void {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text.slice(0, 500));
  u.lang = lang === "en" ? "en-US" : "zh-CN";
  u.rate = 0.95;
  window.speechSynthesis.speak(u);
}

export function startVoiceInput(onResult: (text: string) => void, lang: string): () => void {
  type SpeechRecCtor = new () => {
    lang: string;
    onresult: ((e: { results: { [i: number]: { [j: number]: { transcript: string } } } }) => void) | null;
    start: () => void;
    stop: () => void;
  };
  const win = window as unknown as {
    SpeechRecognition?: SpeechRecCtor;
    webkitSpeechRecognition?: SpeechRecCtor;
  };
  const SR = win.SpeechRecognition || win.webkitSpeechRecognition;
  if (!SR) return () => {};
  const rec = new SR();
  rec.lang = lang === "en" ? "en-US" : "zh-CN";
  rec.onresult = (e) => {
    const t = e.results[0]?.[0]?.transcript;
    if (t) onResult(t);
  };
  rec.start();
  return () => rec.stop();
}
