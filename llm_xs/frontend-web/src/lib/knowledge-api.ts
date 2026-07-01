import { getToken } from "./api";

export type UploadType = "txt" | "pdf" | "image" | "document" | "other";
export type DocStatus = "pending" | "indexed" | "failed";

export interface KnowledgeDocument {
  doc_id: string;
  title: string;
  grade: number;
  subject: string;
  upload_type: UploadType;
  filename: string;
  status: DocStatus;
  chunk_count: number;
  char_count: number;
  error?: string | null;
  created_at: string;
  indexed_at?: string | null;
}

export interface KnowledgeStatus {
  backend: string;
  rag_engine: string;
  embedding_configured: boolean;
  index_count: number;
  library_doc_count: number;
  ready: boolean;
  milvus_uri?: string | null;
  collection?: string | null;
}

export interface KnowledgeSearchHit {
  text: string;
  score: number;
  source: string;
  grade?: number | null;
  subject?: string | null;
  upload_type?: string | null;
  doc_id?: string | null;
}

function authHeaders(json = true): HeadersInit {
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  const token = getToken();
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

export async function fetchKnowledgeStatus(): Promise<KnowledgeStatus> {
  const resp = await fetch("/api/knowledge/status", { headers: authHeaders() });
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json() as Promise<KnowledgeStatus>;
}

export async function fetchKnowledgeDocuments(params?: {
  grade?: number;
  subject?: string;
  upload_type?: string;
}): Promise<KnowledgeDocument[]> {
  const q = new URLSearchParams();
  if (params?.grade) q.set("grade", String(params.grade));
  if (params?.subject) q.set("subject", params.subject);
  if (params?.upload_type) q.set("upload_type", params.upload_type);
  const qs = q.toString();
  const resp = await fetch(`/api/knowledge/documents${qs ? `?${qs}` : ""}`, {
    headers: authHeaders(),
  });
  if (!resp.ok) throw new Error(await resp.text());
  const data = (await resp.json()) as { documents: KnowledgeDocument[] };
  return data.documents;
}

function parseApiError(raw: string, status: number): string {
  try {
    const j = JSON.parse(raw) as {
      detail?: string | { msg?: string }[];
      error?: string;
    };
    if (typeof j.detail === "string") return j.detail;
    if (Array.isArray(j.detail) && j.detail[0]?.msg) return j.detail[0].msg;
    if (j.error) return j.error;
  } catch {
    /* keep raw */
  }
  if (status === 413) return "文件过大，请压缩后重试或换 txt";
  if (status === 401) return "登录已过期，请重新登录";
  return raw || `HTTP ${status}`;
}

export async function uploadKnowledgeFile(
  file: File,
  grade: number,
  subject: string,
  title?: string,
  uploadType?: string,
): Promise<KnowledgeDocument> {
  const form = new FormData();
  form.append("file", file);
  form.append("grade", String(grade));
  form.append("subject", subject);
  if (title) form.append("title", title);
  if (uploadType) form.append("upload_type", uploadType);
  let resp: Response;
  try {
    resp = await fetch("/api/knowledge/upload", {
      method: "POST",
      headers: authHeaders(false),
      body: form,
      signal: AbortSignal.timeout(300_000),
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "TimeoutError") {
      throw new Error("上传超时，文件可能较大，请稍后刷新列表查看是否已入库");
    }
    throw new Error("网络错误，请确认后端已启动（8001）并重试");
  }
  if (!resp.ok) {
    throw new Error(parseApiError(await resp.text(), resp.status));
  }
  const data = (await resp.json()) as { document: KnowledgeDocument };
  return data.document;
}

export async function uploadKnowledgeText(
  content: string,
  grade: number,
  subject: string,
  title: string,
): Promise<KnowledgeDocument> {
  const form = new FormData();
  form.append("content", content);
  form.append("grade", String(grade));
  form.append("subject", subject);
  form.append("title", title);
  form.append("upload_type", "txt");
  const resp = await fetch("/api/knowledge/upload/text", {
    method: "POST",
    headers: authHeaders(false),
    body: form,
  });
  if (!resp.ok) throw new Error(await resp.text());
  const data = (await resp.json()) as { document: KnowledgeDocument };
  return data.document;
}

export async function deleteKnowledgeDocument(docId: string): Promise<void> {
  const resp = await fetch(`/api/knowledge/documents/${encodeURIComponent(docId)}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!resp.ok) throw new Error(await resp.text());
}

export async function reindexKnowledgeDocument(docId: string): Promise<KnowledgeDocument> {
  const resp = await fetch(`/api/knowledge/documents/${encodeURIComponent(docId)}/reindex`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!resp.ok) throw new Error(await resp.text());
  const data = (await resp.json()) as { document: KnowledgeDocument };
  return data.document;
}

export async function rebuildKnowledgeIndex(): Promise<number> {
  const resp = await fetch("/api/knowledge/rebuild", {
    method: "POST",
    headers: authHeaders(),
  });
  if (!resp.ok) throw new Error(await resp.text());
  const data = (await resp.json()) as { index_count: number };
  return data.index_count;
}

export async function searchKnowledge(
  query: string,
  topK = 8,
): Promise<KnowledgeSearchHit[]> {
  const resp = await fetch("/api/knowledge/search", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ query, top_k: topK }),
  });
  if (!resp.ok) throw new Error(await resp.text());
  const data = (await resp.json()) as { hits: KnowledgeSearchHit[] };
  return data.hits;
}
