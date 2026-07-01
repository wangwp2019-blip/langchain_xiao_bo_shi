// Learning domain types (Jarvis v2)

export interface OnboardingProfile {
  student_id: string;
  grade: string;
  grade_level: number;
  subject: string;
  unit_id?: string | null;
  self_assessment?: string | null;
  onboarded_at: string;
}

export interface GapEntry {
  knowledge_point_id: string;
  title: string;
  status: "weak" | "learning" | "mastered" | "unknown";
  correct_streak: number;
  attempt_count: number;
  last_attempt_id?: string | null;
  provenance?: string;
  updated_at?: string;
}

export interface LearningQuestion {
  question_id: string;
  prompt: string;
  knowledge_point_id: string;
  unit_id: string;
  grade: number;
  subject: string;
}

export interface AttemptRecord {
  attempt_id: string;
  student_id: string;
  question_id?: string | null;
  knowledge_point_id: string;
  is_correct: boolean;
  error_code?: string | null;
  source: string;
  prompt: string;
  student_answer: string;
  feedback: string;
  created_at: string;
}

export interface ProgressView {
  student_id: string;
  encouragement: string;
  mastered_titles: string[];
  learning_titles: string[];
  streak_days: number;
  total_attempts: number;
  recent_wins: string[];
}

export interface StudyPlanStep {
  step: number;
  title: string;
  action: string;
  knowledge_point_id?: string | null;
  duration_min: number;
}

export interface StudyPlan {
  plan_id: string;
  student_id: string;
  title: string;
  steps: StudyPlanStep[];
  total_minutes: number;
  created_at: string;
}

export interface PhotoInboxItem {
  inbox_id: string;
  student_id: string;
  text: string;
  suggested_kp_id?: string | null;
  suggested_kp_title: string;
  confidence: number;
  triage: string;
  status: string;
  created_at: string;
  resolved_kp_id?: string | null;
}

export interface ParentReport {
  student_id: string;
  period_days: number;
  summary: string;
  attempts_total?: number;
  correct_rate?: number | null;
  mastered_count?: number;
  weak_count?: number;
  knowledge_section: { kp_id: string; title: string; status: string; attempts: number }[];
  dimension_scores: Record<string, number>;
  habit_notes: string[];
  suggestions: string[];
  evidence: { type: string; id: string; prompt: string; correct: boolean }[];
  generated_at: string;
}

export interface UnitCatalogEntry {
  unit_id: string;
  grade: number;
  subject: string;
  unit_title: string;
  textbook_ref?: string;
  knowledge_points: { knowledge_point_id: string; title: string; description?: string }[];
}

export interface StudyCard {
  topic: string;
  answer: string;
  knowledge_points: string[];
  example: string;
  encouragement: string;
}

export interface VisionItem {
  index: number;
  prompt: string;
  student_answer?: string | null;
  is_correct?: boolean | null;
  knowledge_point_id?: string | null;
}

export interface VisionUnderstandResponse {
  vision_id: string;
  summary: string;
  items: VisionItem[];
  triage: string;
}

export interface KpReviewJob {
  job_id: string;
  status: string;
  diff: { changes: unknown[]; blocking_count: number };
  ready_to_approve: boolean;
  created_at: string;
}

export type AppTab = "chat" | "quiz" | "learn" | "progress" | "plan" | "card" | "wiki";
export type AppMode = "student" | "parent";
