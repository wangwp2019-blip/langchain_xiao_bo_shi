import { useCallback, useEffect, useRef, useState } from "react";
import {
  deleteKnowledgeDocument,
  fetchKnowledgeDocuments,
  fetchKnowledgeStatus,
  rebuildKnowledgeIndex,
  reindexKnowledgeDocument,
  searchKnowledge,
  uploadKnowledgeFile,
  type KnowledgeDocument,
  type KnowledgeSearchHit,
  type KnowledgeStatus,
} from "../lib/knowledge-api";
import { t } from "../lib/i18n";
import type { Lang } from "../lib/types";

interface Props {
  lang: Lang;
}

const GRADES = [1, 2, 3, 4, 5, 6] as const;
const SUBJECTS = ["语文", "数学", "科学", "英语", "道德与法治", "其他"] as const;
const UPLOAD_TYPES = [
  { key: "", labelZh: "全部类型", labelEn: "All types" },
  { key: "txt", labelZh: "文本", labelEn: "Text" },
  { key: "pdf", labelZh: "PDF", labelEn: "PDF" },
  { key: "image", labelZh: "图片", labelEn: "Image" },
  { key: "document", labelZh: "Word 等", labelEn: "Document" },
  { key: "other", labelZh: "其他", labelEn: "Other" },
] as const;

const STATUS_STYLE: Record<string, string> = {
  indexed: "bg-emerald-50 text-emerald-700 border-emerald-100",
  pending: "bg-amber-50 text-amber-800 border-amber-100",
  failed: "bg-red-50 text-red-700 border-red-100",
};

const TYPE_ICON: Record<string, string> = {
  txt: "📄",
  pdf: "📕",
  image: "🖼️",
  document: "📘",
  other: "📦",
};

export function KnowledgeLibraryPanel({ lang }: Props) {
  const zh = lang === "zh";
  const fileRef = useRef<HTMLInputElement>(null);

  const [status, setStatus] = useState<KnowledgeStatus | null>(null);
  const [docs, setDocs] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const [filterGrade, setFilterGrade] = useState<number | "">("");
  const [filterSubject, setFilterSubject] = useState("");
  const [filterType, setFilterType] = useState("");

  const [uploadGrade, setUploadGrade] = useState(2);
  const [uploadSubject, setUploadSubject] = useState("数学");
  const [uploadTitle, setUploadTitle] = useState("");

  const [searchQuery, setSearchQuery] = useState("");
  const [hits, setHits] = useState<KnowledgeSearchHit[]>([]);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [st, list] = await Promise.all([
        fetchKnowledgeStatus(),
        fetchKnowledgeDocuments({
          grade: filterGrade || undefined,
          subject: filterSubject || undefined,
          upload_type: filterType || undefined,
        }),
      ]);
      setStatus(st);
      setDocs(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [filterGrade, filterSubject, filterType]);

  useEffect(() => {
    reload();
  }, [reload]);

  const handleUploadFiles = async (files: FileList | File[]) => {
    const arr = Array.from(files);
    if (!arr.length) return;
    setBusy(true);
    setError(null);
    try {
      for (const file of arr) {
        const title = uploadTitle.trim() || file.name.replace(/\.[^.]+$/, "");
        await uploadKnowledgeFile(file, uploadGrade, uploadSubject, title);
      }
      setUploadTitle("");
      await reload();
      // 后台异步索引时轮询直到 indexed/failed
      for (let i = 0; i < 15; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const list = await fetchKnowledgeDocuments({
          grade: filterGrade || undefined,
          subject: filterSubject || undefined,
          upload_type: filterType || undefined,
        });
        setDocs(list);
        if (!list.some((d) => d.status === "pending")) break;
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.length) handleUploadFiles(e.dataTransfer.files);
  };

  const handleDelete = async (docId: string) => {
    if (!confirm(zh ? "确定删除这份资料吗？" : "Delete this document?")) return;
    setBusy(true);
    try {
      await deleteKnowledgeDocument(docId);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleReindex = async (docId: string) => {
    setBusy(true);
    try {
      await reindexKnowledgeDocument(docId);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleRebuild = async () => {
    if (!confirm(zh ? "将重建全部向量索引，可能需要几分钟，继续？" : "Rebuild full index?")) return;
    setBusy(true);
    try {
      await rebuildKnowledgeIndex();
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const runSearch = async () => {
    const q = searchQuery.trim();
    if (!q) return;
    setBusy(true);
    setHits([]);
    try {
      const data = await searchKnowledge(q);
      setHits(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      {/* 状态栏 */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label={t("kbIndexCount", lang)}
          value={status?.index_count ?? "—"}
          icon="🧠"
        />
        <StatCard
          label={t("kbDocCount", lang)}
          value={status?.library_doc_count ?? "—"}
          icon="📚"
        />
        <StatCard
          label={t("kbBackend", lang)}
          value={status?.backend ?? "—"}
          icon="⚙️"
        />
        <StatCard
          label={t("kbReady", lang)}
          value={
            status?.ready
              ? zh
                ? "就绪"
                : "Ready"
              : zh
                ? "未就绪"
                : "Not ready"
          }
          icon={status?.ready ? "✅" : "⚠️"}
          highlight={status?.ready}
        />
      </div>

      {error && (
        <div className="rounded-xl bg-red-50 border border-red-100 text-red-700 px-4 py-3 text-sm">
          {error}
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-6">
        {/* 上传区 */}
        <section className="glass-card rounded-2xl p-5 space-y-4">
          <h2 className="font-bold text-primary text-lg">{t("kbUploadTitle", lang)}</h2>
          <p className="text-sm text-gray-500">{t("kbUploadHint", lang)}</p>

          <div className="grid grid-cols-2 gap-3">
            <label className="text-xs text-gray-500 space-y-1">
              {t("grade", lang)}
              <select
                className="w-full px-3 py-2 rounded-lg border bg-white text-sm"
                value={uploadGrade}
                onChange={(e) => setUploadGrade(Number(e.target.value))}
              >
                {GRADES.map((g) => (
                  <option key={g} value={g}>
                    {zh ? `${g} 年级` : `Grade ${g}`}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-gray-500 space-y-1">
              {t("subject", lang)}
              <select
                className="w-full px-3 py-2 rounded-lg border bg-white text-sm"
                value={uploadSubject}
                onChange={(e) => setUploadSubject(e.target.value)}
              >
                {SUBJECTS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="text-xs text-gray-500 space-y-1 block">
            {t("kbDocTitle", lang)}
            <input
              className="w-full px-3 py-2 rounded-lg border bg-white text-sm"
              placeholder={zh ? "可选，默认用文件名" : "Optional"}
              value={uploadTitle}
              onChange={(e) => setUploadTitle(e.target.value)}
            />
          </label>

          <div
            role="button"
            tabIndex={0}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => fileRef.current?.click()}
            onKeyDown={(e) => e.key === "Enter" && fileRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition ${
              dragOver
                ? "border-primary bg-primary/5"
                : "border-gray-200 hover:border-primary/40 hover:bg-white/80"
            }`}
          >
            <div className="text-4xl mb-2">📤</div>
            <p className="font-medium text-gray-700">{t("kbDropHint", lang)}</p>
            <p className="text-xs text-gray-400 mt-2">.txt · .pdf · .docx · .png · .jpg</p>
            <input
              ref={fileRef}
              type="file"
              multiple
              accept=".txt,.md,.pdf,.docx,.png,.jpg,.jpeg,.webp"
              className="hidden"
              onChange={(e) => e.target.files && handleUploadFiles(e.target.files)}
            />
          </div>

          {busy && (
            <p className="text-sm text-primary animate-pulse">{t("kbUploading", lang)}</p>
          )}
        </section>

        {/* 检索预览 */}
        <section className="glass-card rounded-2xl p-5 space-y-4">
          <h2 className="font-bold text-primary text-lg">{t("kbSearchTitle", lang)}</h2>
          <div className="flex gap-2">
            <input
              className="flex-1 px-4 py-2.5 rounded-xl border bg-white focus:outline-none focus:border-primary/50 text-sm"
              placeholder={t("kbSearchPlaceholder", lang)}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runSearch()}
            />
            <button
              type="button"
              className="btn-primary px-4 py-2 rounded-lg text-sm disabled:opacity-40"
              disabled={busy || !searchQuery.trim()}
              onClick={runSearch}
            >
              {t("wikiSearch", lang)}
            </button>
          </div>
          <p className="text-xs text-gray-400">
            {zh ? "全库检索，不限年级与学科" : "Search entire library (no grade/subject filter)"}
          </p>

          <div className="space-y-2 max-h-64 overflow-y-auto">
            {hits.map((h, i) => (
              <div
                key={`${h.doc_id}-${i}`}
                className="bg-white rounded-xl p-3 border border-gray-100 text-sm"
              >
                <div className="flex justify-between text-xs text-gray-400 mb-1">
                  <span>{h.source || h.doc_id}</span>
                  <span>{(h.score * 100).toFixed(1)}%</span>
                </div>
                <p className="text-gray-700 line-clamp-3">{h.text}</p>
              </div>
            ))}
            {!hits.length && searchQuery && !busy && (
              <p className="text-sm text-gray-400 text-center py-4">
                {zh ? "暂无命中，试试换关键词" : "No hits"}
              </p>
            )}
          </div>
        </section>
      </div>

      {/* 文档列表 */}
      <section className="glass-card rounded-2xl p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-bold text-primary text-lg">{t("kbListTitle", lang)}</h2>
          <div className="flex gap-2 flex-wrap">
            <select
              className="px-2 py-1.5 rounded-lg border bg-white text-xs"
              value={filterGrade}
              onChange={(e) =>
                setFilterGrade(e.target.value ? Number(e.target.value) : "")
              }
            >
              <option value="">{zh ? "全部年级" : "All grades"}</option>
              {GRADES.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
            <select
              className="px-2 py-1.5 rounded-lg border bg-white text-xs"
              value={filterSubject}
              onChange={(e) => setFilterSubject(e.target.value)}
            >
              <option value="">{zh ? "全部学科" : "All subjects"}</option>
              {SUBJECTS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <select
              className="px-2 py-1.5 rounded-lg border bg-white text-xs"
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
            >
              {UPLOAD_TYPES.map((t) => (
                <option key={t.key || "all"} value={t.key}>
                  {zh ? t.labelZh : t.labelEn}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="px-3 py-1.5 rounded-lg text-xs border border-gray-200 hover:bg-gray-50"
              disabled={busy}
              onClick={handleRebuild}
            >
              {t("kbRebuild", lang)}
            </button>
          </div>
        </div>

        {loading ? (
          <p className="text-center text-gray-500 py-8">{t("loading", lang)}</p>
        ) : docs.length === 0 ? (
          <p className="text-center text-gray-400 py-8">{t("kbEmpty", lang)}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-400 border-b">
                  <th className="pb-2 pr-3">{t("kbDocTitle", lang)}</th>
                  <th className="pb-2 pr-3">{t("grade", lang)}</th>
                  <th className="pb-2 pr-3">{t("subject", lang)}</th>
                  <th className="pb-2 pr-3">{t("kbType", lang)}</th>
                  <th className="pb-2 pr-3">{t("kbStatus", lang)}</th>
                  <th className="pb-2 pr-3">{t("kbChunks", lang)}</th>
                  <th className="pb-2">{t("kbActions", lang)}</th>
                </tr>
              </thead>
              <tbody>
                {docs.map((d) => (
                  <tr key={d.doc_id} className="border-b border-gray-50 hover:bg-white/60">
                    <td className="py-3 pr-3">
                      <div className="font-medium text-gray-800">{d.title}</div>
                      <div className="text-xs text-gray-400 truncate max-w-[200px]">
                        {d.filename}
                      </div>
                    </td>
                    <td className="py-3 pr-3">{d.grade}</td>
                    <td className="py-3 pr-3">{d.subject}</td>
                    <td className="py-3 pr-3">
                      {TYPE_ICON[d.upload_type] || "📦"} {d.upload_type}
                    </td>
                    <td className="py-3 pr-3">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full border ${
                          STATUS_STYLE[d.status] || STATUS_STYLE.pending
                        }`}
                      >
                        {d.status}
                      </span>
                      {d.error && (
                        <div className="text-xs text-red-500 mt-0.5 max-w-[120px] truncate" title={d.error}>
                          {d.error}
                        </div>
                      )}
                    </td>
                    <td className="py-3 pr-3">{d.chunk_count}</td>
                    <td className="py-3">
                      <div className="flex gap-1">
                        {d.status === "failed" && (
                          <button
                            type="button"
                            className="text-xs px-2 py-1 rounded bg-amber-50 text-amber-800 hover:bg-amber-100"
                            disabled={busy}
                            onClick={() => handleReindex(d.doc_id)}
                          >
                            {t("kbReindex", lang)}
                          </button>
                        )}
                        <button
                          type="button"
                          className="text-xs px-2 py-1 rounded bg-red-50 text-red-600 hover:bg-red-100"
                          disabled={busy}
                          onClick={() => handleDelete(d.doc_id)}
                        >
                          {zh ? "删除" : "Del"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
  highlight,
}: {
  label: string;
  value: string | number;
  icon: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-xl p-4 border ${
        highlight ? "bg-emerald-50/80 border-emerald-100" : "bg-white/80 border-gray-100"
      }`}
    >
      <div className="text-2xl mb-1">{icon}</div>
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-lg font-bold text-gray-800 mt-0.5">{value}</div>
    </div>
  );
}
