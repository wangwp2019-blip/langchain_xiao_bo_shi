import type {
  ChatResponse,
  GradeResult,
  Health,
  Lang,
  QuizResponse,
} from "./types";

// ==================== 认证工具 ====================

/** 认证服务地址（页面跳转用，API 请求走 viteite 代理 /auth-api） */
const AUTH_URL = (import.meta.env.VITE_AUTH_URL as string) || "http://localhost:8002";

const TOKEN_KEY = "kid_access_token";
const USER_KEY = "kid_user";
/** token 过期前多少分钟开始续期 */
const REFRESH_THRESHOLD_MIN = 5;

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getAuthUser(): { display_name?: string; email?: string; id?: string } | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/** 设置当前用户信息（登录跨源后前端需自行回填，否则 studentId 会是通用值）。 */
export function setAuthUser(user: { display_name?: string; email?: string; id?: string }): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

/**
 * 登录跳转回来后同步真实用户身份：
 * 1) 先用 JWT 的 sub 兜底写入（保证 studentId 唯一、不再是 web-kid）；
 * 2) 再尝试调用认证服务 /me 拉取昵称等完整资料。
 * localStorage 按源隔离，认证页（:8002）写的 kid_user 在前端源不可见，故必须在此回填。
 */
export async function syncAuthUser(): Promise<void> {
  const token = getToken();
  if (!token) return;
  const existing = getAuthUser();
  const sub = decodeJwtPayload(token)?.sub;
  if (sub && !existing?.id) {
    setAuthUser({ ...(existing || {}), id: sub });
  }
  try {
    const resp = await fetch("/auth-api/me", { headers: { Authorization: `Bearer ${token}` } });
    if (resp.ok) {
      const me = await resp.json();
      setAuthUser({
        id: String(me.id ?? sub ?? ""),
        email: me.email,
        display_name: me.display_name ?? me.name,
      });
    }
  } catch {
    // /me 不可用时保留 JWT sub 兜底，不影响使用
  }
}

/** 解码 JWT 的 payload（不验证签名，仅读取 exp / sub） */
function decodeJwtPayload(token: string): { exp?: number; sub?: string } | null {
  try {
    const payload = token.split(".")[1];
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

/** token 是否存在且未过期 */
export function isTokenValid(): boolean {
  const token = getToken();
  if (!token) return false;
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) return false;
  return Date.now() < payload.exp * 1000;
}

/** token 是否快过期（需要续期） */
export function isTokenExpiringSoon(): boolean {
  const token = getToken();
  if (!token) return false;
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) return false;
  const remainingMin = (payload.exp * 1000 - Date.now()) / 60000;
  return remainingMin < REFRESH_THRESHOLD_MIN;
}

/** 用 refresh_token 刷新 access_token，实现续期 */
export async function refreshToken(): Promise<boolean> {
  const token = getToken();
  if (!token) return false;
  try {
    const resp = await fetch("/auth-api/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: token }),
    });
    if (!resp.ok) return false;
    const data = await resp.json();
    if (data.access_token) {
      setToken(data.access_token);
      if (data.user) {
        localStorage.setItem(USER_KEY, JSON.stringify(data.user));
      }
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

/** 跳转到认证服务登录页 */
export function redirectToLogin(): void {
  clearAuth();
  const callback = window.location.origin + window.location.pathname;
  window.location.href = `${AUTH_URL}/?redirect=${encodeURIComponent(callback)}`;
}

/** 从 URL hash 读取登录跳转带来的 token */
export function consumeHashToken(): string | null {
  const hash = window.location.hash;
  if (!hash) return null;
  const match = hash.match(/[#&]token=([^&]+)/);
  if (!match) return null;
  const token = decodeURIComponent(match[1]);
  // 清掉 hash，避免刷新重复读取
  history.replaceState(null, "", window.location.pathname + window.location.search);
  return token;
}

// ==================== API 请求 ====================

const FETCH_TIMEOUT_MS = Number(import.meta.env.VITE_FETCH_TIMEOUT_MS || 120_000);
const FETCH_RETRIES = Number(import.meta.env.VITE_FETCH_RETRIES || 2);

function headers(): HeadersInit {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) {
    h["Authorization"] = `Bearer ${token}`;
  }
  return h;
}

async function fetchWithRetry(
  input: RequestInfo | URL,
  init?: RequestInit,
  retries = FETCH_RETRIES,
): Promise<Response> {
  let lastError: unknown;
  for (let i = 0; i <= retries; i++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    try {
      const resp = await fetch(input, { ...init, signal: controller.signal });
      clearTimeout(timer);
      // 401 → token 失效，跳转登录
      if (resp.status === 401) {
        redirectToLogin();
        throw new Error("未登录或登录已过期");
      }
      if (resp.status >= 500 && i < retries) {
        await new Promise((r) => setTimeout(r, 500 * (i + 1)));
        continue;
      }
      return resp;
    } catch (e) {
      clearTimeout(timer);
      lastError = e;
      if (i < retries) await new Promise((r) => setTimeout(r, 500 * (i + 1)));
    }
  }
  throw lastError ?? new Error("network error");
}

/** 从非 2xx 响应中提取后端友好错误信息（兼容 {error} 与 {detail}）。 */
async function extractError(resp: Response): Promise<string> {
  try {
    const data = await resp.json();
    return (
      data?.error ||
      data?.detail ||
      data?.message ||
      `请求失败（${resp.status}）`
    );
  } catch {
    return `请求失败（${resp.status}）`;
  }
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetchWithRetry(path, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    throw new Error(await extractError(resp));
  }
  return (await resp.json()) as T;
}

export async function getHealth(): Promise<Health> {
  const resp = await fetchWithRetry("/api/health", { headers: headers() });
  return (await resp.json()) as Health;
}

export async function chat(
  question: string,
  userId: string,
  threadId: string,
): Promise<ChatResponse> {
  return postJSON<ChatResponse>("/api/chat", {
    question,
    user_id: userId,
    thread_id: threadId,
  });
}

export async function chatStream(
  question: string,
  userId: string,
  threadId: string,
  onChunk: (text: string) => void,
): Promise<void> {
  const resp = await fetchWithRetry("/api/chat/stream", {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ question, user_id: userId, thread_id: threadId }),
  });
  if (!resp.body) {
    const data = await resp.json().catch(() => ({}));
    onChunk((data as ChatResponse).answer || "(无回复)");
    return;
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";
    for (const frame of frames) {
      if (frame.startsWith("event: done")) continue;
      const text = frame
        .split("\n")
        .filter((l) => l.startsWith("data: "))
        .map((l) => l.slice(6))
        .join("\n");
      if (text && text !== "[DONE]") onChunk(text);
    }
  }
}

export async function createQuiz(
  grade: string,
  subject: string,
  count: number,
): Promise<QuizResponse> {
  return postJSON<QuizResponse>("/api/quiz", { grade, subject, count });
}

export async function gradeQuiz(
  sessionId: string,
  answers: Record<string, string>,
): Promise<GradeResult> {
  return postJSON<GradeResult>("/api/grade", {
    session_id: sessionId,
    answers,
  });
}

export interface PrivacyPolicy {
  version: string;
  title: string;
  summary: string;
  require_consent: boolean;
  data_collected: string[];
  data_retention_days?: number;
}

export interface ConsentStatus {
  user_id: string;
  required: boolean;
  valid: boolean;
  policy_version: string;
}

export async function getPrivacyPolicy(): Promise<PrivacyPolicy> {
  const resp = await fetchWithRetry("/api/privacy/policy", { headers: headers() });
  if (!resp.ok) throw new Error(await extractError(resp));
  return (await resp.json()) as PrivacyPolicy;
}

export async function getConsentStatus(sub: string): Promise<ConsentStatus> {
  const resp = await fetchWithRetry(`/api/privacy/consent?sub=${encodeURIComponent(sub)}`, {
    headers: headers(),
  });
  if (!resp.ok) throw new Error(await extractError(resp));
  return (await resp.json()) as ConsentStatus;
}

export async function recordConsent(sub: string, parentName: string): Promise<void> {
  await postJSON("/api/privacy/consent", { sub, parent_name: parentName });
}

export interface SuggestedPrompt {
  text: string;
  category: string;
}

export async function fetchPromptSuggestions(
  lang: Lang,
  grade?: string,
): Promise<SuggestedPrompt[]> {
  const q = new URLSearchParams({ lang, limit: "6" });
  if (grade) q.set("grade", grade);
  const resp = await fetchWithRetry(`/api/prompts/suggestions?${q}`, { headers: headers() });
  if (!resp.ok) return [];
  const data = (await resp.json()) as { prompts: SuggestedPrompt[] };
  return data.prompts ?? [];
}
