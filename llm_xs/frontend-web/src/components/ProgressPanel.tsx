import { useEffect, useState } from "react";
import {
  fetchDimensions,
  fetchProgress,
  fetchProactive,
  fetchRemediation,
} from "../lib/learning-api";
import { t } from "../lib/i18n";
import type { Lang } from "../lib/types";
import type { ProgressView } from "../lib/learning-types";

interface Props {
  lang: Lang;
  studentId: string;
}

interface Dimensions {
  scores: Record<string, number>;
  behavior_tags: string[];
}

interface Proactive {
  messages: { message: string; kind: string; created_at: string }[];
  recurrence_reminder: string | null;
}

interface Remediation {
  skills: {
    kp_id: string;
    title: string;
    strategy: string;
    success_count: number;
    promoted: boolean;
  }[];
}

const DIMENSION_ICON: Record<string, string> = {
  基础知识: "📚",
  逻辑推理: "🧩",
  审题能力: "👁️",
  细心程度: "🔍",
  学习习惯: "🌱",
};

export function ProgressPanel({ lang, studentId }: Props) {
  const [data, setData] = useState<ProgressView | null>(null);
  const [dims, setDims] = useState<Dimensions | null>(null);
  const [proactive, setProactive] = useState<Proactive | null>(null);
  const [remed, setRemed] = useState<Remediation | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchProgress(studentId).catch(() => null),
      fetchDimensions(studentId).catch(() => null),
      fetchProactive(studentId, 5).catch(() => null),
      fetchRemediation(studentId).catch(() => null),
    ])
      .then(([p, d, pr, r]) => {
        setData(p);
        setDims(d);
        setProactive(pr);
        setRemed(r);
      })
      .finally(() => setLoading(false));
  }, [studentId]);

  if (loading) {
    return <div className="p-8 text-center text-gray-500">{t("loading", lang)}</div>;
  }

  if (!data) {
    return <div className="p-8 text-center text-gray-500">{t("progressEmpty", lang)}</div>;
  }

  const zh = lang === "zh";

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      {/* 鼓励卡 */}
      <div className="rounded-2xl bg-gradient-to-br from-primary/90 to-primary p-6 text-white shadow-lg">
        <div className="text-3xl mb-2">🏆</div>
        <p className="text-lg font-medium leading-relaxed">{data.encouragement}</p>
        <div className="flex flex-wrap gap-x-6 gap-y-1 mt-4 text-sm opacity-90">
          <span>📝 {t("progressAttempts", lang)}: {data.total_attempts}</span>
          <span>🔥 {t("progressStreak", lang)}: {data.streak_days} {t("days", lang)}</span>
        </div>
      </div>

      {/* 主动提醒 */}
      {proactive?.recurrence_reminder && (
        <section className="rounded-xl bg-amber-50 border border-amber-200 p-4 animate-fade-in">
          <div className="flex items-start gap-2">
            <span className="text-xl">💡</span>
            <div>
              <p className="font-medium text-amber-800 text-sm">{proactive.recurrence_reminder}</p>
            </div>
          </div>
        </section>
      )}

      {/* 已掌握 / 进步中 */}
      <div className="grid sm:grid-cols-2 gap-4">
        {data.mastered_titles.length > 0 && (
          <section className="glass-card rounded-xl p-5">
            <h3 className="font-semibold text-green-600 mb-3">✨ {t("progressMastered", lang)}</h3>
            <div className="flex flex-wrap gap-2">
              {data.mastered_titles.map((title) => (
                <span
                  key={title}
                  className="px-3 py-1.5 rounded-full bg-green-50 text-green-700 text-sm border border-green-100"
                >
                  {title}
                </span>
              ))}
            </div>
          </section>
        )}
        {data.learning_titles.length > 0 && (
          <section className="glass-card rounded-xl p-5">
            <h3 className="font-semibold text-amber-600 mb-3">🌱 {t("progressLearning", lang)}</h3>
            <div className="flex flex-wrap gap-2">
              {data.learning_titles.map((title) => (
                <span
                  key={title}
                  className="px-3 py-1.5 rounded-full bg-amber-50 text-amber-800 text-sm border border-amber-100"
                >
                  {title}
                </span>
              ))}
            </div>
          </section>
        )}
      </div>

      {/* 能力维度 */}
      {dims && Object.keys(dims.scores).length > 0 && (
        <section className="glass-card rounded-xl p-5">
          <h3 className="font-semibold text-primary mb-3">🧠 {zh ? "能力维度" : "Skill dimensions"}</h3>
          <div className="grid sm:grid-cols-2 gap-4">
            {Object.entries(dims.scores).map(([k, v]) => (
              <div key={k} className="text-sm">
                <div className="flex justify-between mb-1.5">
                  <span className="text-gray-700">
                    {DIMENSION_ICON[k] || "•"} {k}
                  </span>
                  <span className="text-gray-500">{Math.round(v * 100)}%</span>
                </div>
                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-primary to-primary/70 rounded-full transition-all"
                    style={{ width: `${Math.max(v * 100, 6)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
          {dims.behavior_tags.length > 0 && (
            <div className="mt-4 pt-3 border-t border-gray-100 flex flex-wrap gap-2">
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
        </section>
      )}

      {/* 个人补救策略 */}
      {remed && remed.skills.length > 0 && (
        <section className="glass-card rounded-xl p-5">
          <h3 className="font-semibold text-indigo-600 mb-3">
            🎯 {zh ? "我的小妙招" : "My strategies"}
          </h3>
          <ul className="space-y-2 text-sm">
            {remed.skills.map((s) => (
              <li
                key={s.kp_id}
                className="flex items-start gap-2 p-3 rounded-lg bg-indigo-50/50 border border-indigo-100"
              >
                <span className="shrink-0">{s.promoted ? "⭐" : "📌"}</span>
                <div>
                  <p className="font-medium text-gray-800">{s.title}</p>
                  <p className="text-xs text-gray-600 mt-0.5">{s.strategy}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 最近亮点 */}
      <section className="glass-card rounded-xl p-5">
        <h3 className="font-semibold text-gray-700 mb-2">💬 {t("progressRecent", lang)}</h3>
        <ul className="space-y-2 text-sm text-gray-600">
          {data.recent_wins.map((w, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-primary">·</span>
              <span>{w}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* 历史主动消息 */}
      {proactive && proactive.messages.length > 0 && (
        <section className="glass-card rounded-xl p-5">
          <h3 className="font-semibold text-gray-700 mb-2">🔔 {zh ? "小博士提醒" : "Jarvis tips"}</h3>
          <ul className="space-y-2 text-sm text-gray-600">
            {proactive.messages.slice(-3).reverse().map((m, i) => (
              <li key={i} className="flex gap-2">
                <span>·</span>
                <span>{m.message}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
