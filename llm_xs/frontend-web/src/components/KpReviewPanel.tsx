import { useEffect, useState } from "react";
import {
  approveKpReviewJob,
  fetchIngestJobs,
  fetchKpReviewJobs,
  promoteIngest,
  submitIngest,
  submitKpReview,
} from "../lib/learning-api";
import { t } from "../lib/i18n";
import type { Lang } from "../lib/types";
import type { KpReviewJob } from "../lib/learning-types";
import type { TextbookIngestJob } from "../lib/learning-api";

interface Props {
  lang: Lang;
}

interface Change {
  type: string;
  kp_id?: string;
  title?: string;
  old?: string;
  new?: string;
  unit_id?: string;
}

const CHANGE_LABEL: Record<string, { zh: string; en: string; color: string }> = {
  new_unit: { zh: "新增单元", en: "New unit", color: "text-green-600" },
  new_kp: { zh: "新增知识点", en: "New KP", color: "text-green-600" },
  title_changed: { zh: "标题变更", en: "Title changed", color: "text-amber-600" },
  missing_in_draft: { zh: "草稿缺失", en: "Missing in draft", color: "text-red-600" },
};

const SAMPLE = `---
学科: 数学
年级: 2
教材版本: 人教版·二年级上册
---

# 单元：100以内的加法和减法（二）

unit_id: math-g2-add-sub-100

## 知识点

- 进位加法 → kp-g2-add-carry
  说明: 个位满十向十位进 1

- 退位减法 → kp-g2-sub-borrow
  说明: 个位不够减，从十位退 1 当 10
`;

export function KpReviewPanel({ lang }: Props) {
  const [jobs, setJobs] = useState<KpReviewJob[]>([]);
  const [ingestJobs, setIngestJobs] = useState<TextbookIngestJob[]>([]);
  const [content, setContent] = useState("");
  const [ingestContent, setIngestContent] = useState("");
  const [ingestSubject, setIngestSubject] = useState("数学");
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const zh = lang === "zh";

  const reload = () => {
    fetchKpReviewJobs().then(setJobs).catch(() => {});
    fetchIngestJobs().then(setIngestJobs).catch(() => {});
  };

  useEffect(() => {
    reload();
  }, []);

  const handleSubmit = async () => {
    if (!content.trim()) return;
    setBusy(true);
    try {
      await submitKpReview(content);
      setContent("");
      reload();
    } finally {
      setBusy(false);
    }
  };

  const handleApprove = async (jobId: string) => {
    setBusy(true);
    try {
      await approveKpReviewJob(jobId);
      reload();
    } finally {
      setBusy(false);
    }
  };

  const handleIngest = async () => {
    if (!ingestContent.trim()) return;
    setBusy(true);
    try {
      await submitIngest(ingestContent, { subject: ingestSubject });
      setIngestContent("");
      reload();
    } finally {
      setBusy(false);
    }
  };

  const handlePromote = async (jobId: string) => {
    setBusy(true);
    try {
      await promoteIngest(jobId);
      reload();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="glass-card rounded-xl p-5 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h3 className="font-bold text-primary">📚 KP 目录审核</h3>
          <button
            type="button"
            className="text-xs px-2 py-1 rounded border border-gray-200 hover:bg-gray-50"
            onClick={() => setContent(SAMPLE)}
          >
            {zh ? "插入样例" : "Insert sample"}
          </button>
        </div>
        <p className="text-sm text-gray-500">
          {zh
            ? "上传 kp.md 文档，系统会与当前目录做 diff；无阻塞项时可批准生效。"
            : "Upload kp.md to diff against the catalog; approve when no blocking changes."}
        </p>
        <textarea
          className="w-full h-44 p-3 rounded-xl border border-gray-200 text-sm font-mono bg-white focus:outline-none focus:border-primary/50"
          placeholder={zh ? "粘贴 kp.md 内容…" : "Paste kp.md content…"}
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
        <button
          type="button"
          disabled={busy || !content.trim()}
          className="btn-primary px-4 py-2 rounded-xl text-sm disabled:opacity-40"
          onClick={handleSubmit}
        >
          {zh ? "提交审核" : "Submit review"}
        </button>
      </div>

      <div className="space-y-3">
        <h4 className="text-sm font-semibold text-gray-600 px-1">
          {zh ? "审核任务" : "Review jobs"} ({jobs.length})
        </h4>
        {jobs.length === 0 ? (
          <p className="text-gray-400 text-center py-8">{t("loading", lang)}</p>
        ) : (
          jobs.map((job) => {
            const changes = (job.diff?.changes || []) as Change[];
            const blocking = job.diff?.blocking_count ?? 0;
            const isOpen = expanded === job.job_id;
            return (
              <div
                key={job.job_id}
                className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm"
              >
                <button
                  type="button"
                  className="w-full text-left flex flex-wrap items-center justify-between gap-2"
                  onClick={() => setExpanded(isOpen ? null : job.job_id)}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">
                      {new Date(job.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${
                        job.status === "approved"
                          ? "bg-green-50 text-green-700"
                          : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {job.status}
                    </span>
                    <span className="text-xs text-gray-500">
                      {zh ? "变更" : "Changes"}: {changes.length} ·{" "}
                      <span className={blocking > 0 ? "text-red-500 font-medium" : ""}>
                        {zh ? "阻塞" : "Block"}: {blocking}
                      </span>
                    </span>
                    <span className="text-gray-400">{isOpen ? "▼" : "▶"}</span>
                  </div>
                </button>

                {isOpen && (
                  <div className="mt-3 pt-3 border-t border-gray-100 space-y-1.5 animate-fade-in">
                    {changes.length === 0 ? (
                      <p className="text-xs text-gray-400">
                        {zh ? "无变更，与目录一致。" : "No changes."}
                      </p>
                    ) : (
                      changes.map((c, i) => {
                        const lbl = CHANGE_LABEL[c.type] || {
                          zh: c.type,
                          en: c.type,
                          color: "text-gray-600",
                        };
                        return (
                          <div key={i} className={`text-xs ${lbl.color}`}>
                            <span className="font-medium">{zh ? lbl.zh : lbl.en}</span>
                            {c.title && <span> · {c.title}</span>}
                            {c.kp_id && <span className="text-gray-400"> ({c.kp_id})</span>}
                            {c.old && c.new && (
                              <span className="text-gray-500">
                                {" "}: {c.old} → {c.new}
                              </span>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                )}

                {job.ready_to_approve && job.status === "pending_review" && (
                  <button
                    type="button"
                    disabled={busy}
                    className="mt-3 text-xs btn-primary px-3 py-1.5 rounded-lg"
                    onClick={() => handleApprove(job.job_id)}
                  >
                    {zh ? "批准生效" : "Approve"}
                  </button>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* 教材 Ingest */}
      <div className="glass-card rounded-xl p-5 space-y-3 mt-6">
        <h3 className="font-bold text-primary">📚 {zh ? "教材 Ingest" : "Textbook Ingest"}</h3>
        <p className="text-sm text-gray-500">
          {zh
            ? "上传教材文本（PDF 抽取/拍照 OCR/文档粘贴），生成 ingest job；可「转入 KP 审核」走审核流。"
            : "Upload textbook text → ingest job → promote to KP review."}
        </p>
        <div className="flex gap-2 flex-wrap">
          <select
            className="px-3 py-2 rounded-lg border bg-white text-sm"
            value={ingestSubject}
            onChange={(e) => setIngestSubject(e.target.value)}
          >
            {["数学", "语文"].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </div>
        <textarea
          className="w-full h-32 p-3 rounded-xl border border-gray-200 text-sm font-mono bg-white focus:outline-none focus:border-primary/50"
          placeholder={zh ? "粘贴教材文本…" : "Paste textbook content…"}
          value={ingestContent}
          onChange={(e) => setIngestContent(e.target.value)}
        />
        <button
          type="button"
          disabled={busy || !ingestContent.trim()}
          className="btn-primary px-4 py-2 rounded-xl text-sm disabled:opacity-40"
          onClick={handleIngest}
        >
          {zh ? "提交 Ingest" : "Submit ingest"}
        </button>

        {ingestJobs.length > 0 && (
          <div className="pt-3 border-t border-gray-100 space-y-2">
            {ingestJobs.slice(0, 5).map((j) => (
              <div
                key={j.job_id}
                className="bg-white rounded-lg p-3 border border-gray-100 flex flex-wrap items-center justify-between gap-2"
              >
                <div className="min-w-0">
                  <div className="text-xs text-gray-400">{j.job_id}</div>
                  <p className="text-sm text-gray-700 line-clamp-2 mt-0.5">
                    {j.extracted_text_preview}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100">
                    {j.status}
                  </span>
                  {j.status === "pending_review" && (
                    <button
                      type="button"
                      disabled={busy}
                      className="text-xs px-2.5 py-1 rounded border border-primary/40 text-primary hover:bg-primary/10"
                      onClick={() => handlePromote(j.job_id)}
                    >
                      {zh ? "转入 KP 审核" : "Promote"}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
