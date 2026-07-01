import { useEffect, useState } from "react";
import {
  fetchGaps,
  fetchParentProfile,
  fetchParentReport,
  overrideGap,
  resolveInbox,
} from "../lib/learning-api";
import { t } from "../lib/i18n";
import type { Lang } from "../lib/types";
import type { GapEntry, ParentReport, PhotoInboxItem } from "../lib/learning-types";
import { KpReviewPanel } from "./KpReviewPanel";
import { KnowledgeLibraryPanel } from "./KnowledgeLibraryPanel";

interface Props {
  lang: Lang;
  studentId: string;
}

const STATUS_COLOR: Record<string, string> = {
  weak: "bg-red-50 text-red-700 border-red-100",
  learning: "bg-amber-50 text-amber-800 border-amber-100",
  mastered: "bg-green-50 text-green-700 border-green-100",
  unknown: "bg-gray-50 text-gray-600 border-gray-100",
};

export function ParentDashboard({ lang, studentId }: Props) {
  const [gaps, setGaps] = useState<GapEntry[]>([]);
  const [inbox, setInbox] = useState<PhotoInboxItem[]>([]);
  const [report, setReport] = useState<ParentReport | null>(null);
  const [dims, setDims] = useState<{ scores: Record<string, number>; behavior_tags: string[] } | null>(null);
  const [tab, setTab] = useState<"gaps" | "inbox" | "report" | "kp-review" | "knowledge">("gaps");
  const [loading, setLoading] = useState(true);

  const reload = async () => {
    setLoading(true);
    try {
      const [g, prof, rep] = await Promise.all([
        fetchGaps(studentId),
        fetchParentProfile(studentId),
        fetchParentReport(studentId),
      ]);
      setGaps(g);
      setInbox(prof.inbox);
      setReport(rep);
      setDims({
        scores: (prof as { dimension_scores?: Record<string, number> }).dimension_scores || {},
        behavior_tags: (prof as { behavior_tags?: string[] }).behavior_tags || [],
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
  }, [studentId]);

  const handleResolve = async (id: string, action: "attach" | "ignore", kpId?: string) => {
    await resolveInbox(id, action, kpId);
    reload();
  };

  const handleOverride = async (kpId: string, status: GapEntry["status"]) => {
    await overrideGap(studentId, kpId, status, "家长订正");
    reload();
  };

  if (loading) {
    return <div className="p-8 text-center text-gray-500">{t("loading", lang)}</div>;
  }

  return (
    <div className="h-full flex flex-col">
      <nav className="flex gap-1 px-5 pt-3 border-b border-gray-100 bg-white/40">
        {(
          [
            ["gaps", t("parentTabGaps", lang)],
            ["inbox", `${t("parentTabInbox", lang)} (${inbox.length})`],
            ["report", t("parentTabReport", lang)],
            ["kp-review", lang === "zh" ? "KP 审核" : "KP Review"],
            ["knowledge", t("parentTabKnowledge", lang)],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition ${
              tab === key ? "bg-white text-primary shadow-sm" : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {tab === "gaps" && (
          <>
            <p className="text-sm text-gray-500">{t("parentGapsHint", lang)}</p>
            {dims && dims.behavior_tags.length > 0 && (
              <div className="flex flex-wrap gap-2 py-1">
                {dims.behavior_tags.map((tag, i) => (
                  <span
                    key={i}
                    className="text-xs px-2.5 py-1 rounded-full bg-primary/10 text-primary"
                  >
                    #{tag}
                  </span>
                ))}
              </div>
            )}
            {gaps.length === 0 ? (
              <p className="text-gray-400 text-center py-12">{t("parentGapsEmpty", lang)}</p>
            ) : (
              gaps.map((g) => (
                <div
                  key={g.knowledge_point_id}
                  className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm flex flex-wrap items-center justify-between gap-3"
                >
                  <div>
                    <div className="font-medium">{g.title}</div>
                    <div className="text-xs text-gray-400 mt-1">
                      {g.knowledge_point_id} · {t("attempts", lang)} {g.attempt_count}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-1 rounded-full border ${STATUS_COLOR[g.status]}`}>
                      {g.status}
                    </span>
                    {g.status !== "mastered" && (
                      <button
                        className="text-xs px-2 py-1 rounded border border-green-200 text-green-700 hover:bg-green-50"
                        onClick={() => handleOverride(g.knowledge_point_id, "mastered")}
                      >
                        {t("parentMarkMastered", lang)}
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </>
        )}

        {tab === "inbox" && (
          <>
            {inbox.length === 0 ? (
              <p className="text-gray-400 text-center py-12">{t("parentInboxEmpty", lang)}</p>
            ) : (
              inbox.map((item) => (
                <div key={item.inbox_id} className="bg-white rounded-xl p-4 border shadow-sm space-y-3">
                  <p className="text-sm text-gray-700 line-clamp-3">{item.text}</p>
                  <p className="text-xs text-gray-400">
                    {t("parentSuggested", lang)}: {item.suggested_kp_title || "—"} (
                    {Math.round(item.confidence * 100)}%)
                  </p>
                  <div className="flex gap-2">
                    <button
                      className="text-sm px-3 py-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/20"
                      onClick={() =>
                        handleResolve(item.inbox_id, "attach", item.suggested_kp_id || undefined)
                      }
                    >
                      {t("parentAttach", lang)}
                    </button>
                    <button
                      className="text-sm px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50"
                      onClick={() => handleResolve(item.inbox_id, "ignore")}
                    >
                      {t("parentIgnore", lang)}
                    </button>
                  </div>
                </div>
              ))
            )}
          </>
        )}

        {tab === "report" && report && (
          <div className="space-y-5">
            <div className="rounded-xl bg-header text-white p-5">
              <h3 className="font-bold text-lg mb-2">{t("parentReportTitle", lang)}</h3>
              <p className="text-sm opacity-90 leading-relaxed">{report.summary}</p>
              {(report.attempts_total !== undefined || report.correct_rate !== null) && (
                <div className="flex flex-wrap gap-x-6 gap-y-1 mt-3 text-sm opacity-90">
                  {report.attempts_total !== undefined && (
                    <span>📝 {lang === "zh" ? "练习" : "Attempts"}: {report.attempts_total}</span>
                  )}
                  {report.correct_rate !== null && report.correct_rate !== undefined && (
                    <span>✅ {lang === "zh" ? "正确率" : "Accuracy"}: {Math.round((report.correct_rate ?? 0) * 100)}%</span>
                  )}
                  {report.mastered_count !== undefined && (
                    <span>🌟 {lang === "zh" ? "已掌握" : "Mastered"}: {report.mastered_count}</span>
                  )}
                  {report.weak_count !== undefined && (
                    <span>💪 {lang === "zh" ? "需巩固" : "Weak"}: {report.weak_count}</span>
                  )}
                </div>
              )}
            </div>
            <section className="glass-card rounded-xl p-4">
              <h4 className="font-semibold mb-3">{t("parentDimensions", lang)}</h4>
              <div className="grid grid-cols-2 gap-3">
                {Object.entries(report.dimension_scores).map(([k, v]) => (
                  <div key={k} className="text-sm">
                    <div className="flex justify-between mb-1">
                      <span>{k}</span>
                      <span>{Math.round(v * 100)}%</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-primary rounded-full" style={{ width: `${v * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </section>
            <section className="glass-card rounded-xl p-4">
              <h4 className="font-semibold mb-2">{t("parentSuggestions", lang)}</h4>
              <ul className="text-sm text-gray-600 space-y-1 list-disc pl-5">
                {report.suggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </section>
            {report.evidence.length > 0 && (
              <section className="glass-card rounded-xl p-4">
                <h4 className="font-semibold mb-2">{lang === "zh" ? "练习证据" : "Evidence"}</h4>
                <ul className="text-sm space-y-2">
                  {report.evidence.map((ev) => (
                    <li
                      key={ev.id}
                      className="flex items-start gap-2 p-2 rounded-lg bg-gray-50 border border-gray-100"
                    >
                      <span>{ev.correct ? "✓" : "✗"}</span>
                      <span className="text-gray-700 line-clamp-2">{ev.prompt}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}

        {tab === "kp-review" && <KpReviewPanel lang={lang} />}

        {tab === "knowledge" && <KnowledgeLibraryPanel lang={lang} />}
      </div>
    </div>
  );
}
