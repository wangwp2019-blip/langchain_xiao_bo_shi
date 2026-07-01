export interface Health {
  status: string;
  mode: "online" | "offline";
  index_count: number;
  vector_backend: string;
  rag_engine?: string;
  memory_backend: string;
  short_term_backend: string;
  llm_model: string;
  llm_configured: boolean;
  embedding_configured: boolean;
  web_search_enabled: boolean;
  tavily_enabled?: boolean;
  google_search_enabled?: boolean;
  moderation_enabled?: boolean;
  auth_enabled: boolean;
  require_parent_consent?: boolean;
  simple_chat_mode?: boolean;
  knowledge_scope_filter?: boolean;
  tracing?: { langsmith: boolean; opentelemetry: boolean };
}
export interface ChatResponse {
  answer?: string;
  error?: string;
  mode?: string;
}

export interface QuizQuestion {
  index: number;
  prompt: string;
  answer: string;
  explanation?: string;
}

export interface Quiz {
  grade: string;
  subject: string;
  questions: QuizQuestion[];
}

export interface QuizQuestionPublic {
  index: number;
  prompt: string;
}

export interface QuizPublic {
  grade: string;
  subject: string;
  questions: QuizQuestionPublic[];
}

export interface QuizResponse {
  session_id: string;
  public: QuizPublic;
}

export interface GradedItem {
  index: number;
  prompt: string;
  user_answer: string;
  correct_answer: string;
  is_correct: boolean;
  feedback: string;
  explanation: string;
}

export interface GradeResult {
  total: number;
  correct: number;
  score: number;
  summary: string;
  items: GradedItem[];
}

export type Lang = "zh" | "en";

/** 12 套适龄主题，通过 data-theme 切换 CSS 变量 */
export type ThemeName =
  | "ocean"
  | "candy"
  | "forest"
  | "sunset"
  | "lavender"
  | "mint"
  | "peach"
  | "sky"
  | "rose"
  | "lemon"
  | "galaxy"
  | "aurora";

/** 主题元数据：用于色卡选择器 */
export interface ThemeMeta {
  name: ThemeName;
  /** 主题色卡预览（渐变 CSS） */
  swatch: string;
}
