import { useState } from "react";
import {
  fetchPushQueue,
  rebuildPushQueue,
  suggestLearningQuestions,
  submitLearningAttempt,
} from "../lib/learning-api";
import { t } from "../lib/i18n";
import type { Lang } from "../lib/types";
import type { AttemptRecord, LearningQuestion } from "../lib/learning-types";

interface Props {
  lang: Lang;
  studentId: string;
}

type Mode = "weak" | "queue";

export function LearningQuizPanel({ lang, studentId }: Props) {
  const [mode, setMode] = useState<Mode>("weak");
  const [questions, setQuestions] = useState<LearningQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [results, setResults] = useState<Record<string, AttemptRecord>>({});
  const [busy, setBusy] = useState(false);
  const zh = lang === "zh";

  const reset = () => {
    setQuestions([]);
    setAnswers({});
    setResults({});
  };

  const loadWeak = async () => {
    setBusy(true);
    reset();
    try {
      setQuestions(await suggestLearningQuestions(studentId, 3));
    } finally {
      setBusy(false);
    }
  };

  const loadQueue = async () => {
    setBusy(true);
    setMode("queue");
    reset();
    try {
      const qs = await fetchPushQueue(studentId, 3);
      if (qs.length === 0) {
        await rebuildPushQueue(studentId, 5);
        setQuestions(await fetchPushQueue(studentId, 3));
      } else {
        setQuestions(qs);
      }
    } finally {
      setBusy(false);
    }
  };

  const submitOne = async (q: LearningQuestion) => {
    const ans = answers[q.question_id] || "";
    if (!ans || busy) return;
    setBusy(true);
    try {
      const r = await submitLearningAttempt(studentId, q.question_id, ans);
      setResults((m) => ({ ...m, [q.question_id]: r }));
    } finally {
      setBusy(false);
    }
  };

  const submitAll = async () => {
    setBusy(true);
    try {
      for (const q of questions) {
        const ans = answers[q.question_id] || "";
        if (ans && !results[q.question_id]) {
          const r = await submitLearningAttempt(studentId, q.question_id, ans);
          setResults((m) => ({ ...m, [q.question_id]: r }));
        }
      }
    } finally {
      setBusy(false);
    }
  };

  const correctCount = Object.values(results).filter((r) => r.is_correct).length;

  return (
    <div className="h-full overflow-y-auto p-5 space-y-5">
      {/* 模式切换 + 操作栏 */}
      <div className="glass-card rounded-xl p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-bold text-primary">{t("learnQuizTitle", lang)}</h2>
            <p className="text-xs text-gray-500">{t("learnQuizHint", lang)}</p>
          </div>
          <div className="flex rounded-lg overflow-hidden border border-gray-200 text-sm">
            <button
              className={`px-3 py-1.5 transition ${mode === "weak" ? "bg-primary text-white" : "bg-white hover:bg-gray-50"}`}
              onClick={() => setMode("weak")}
            >
              {zh ? "薄弱点" : "Weak"}
            </button>
            <button
              className={`px-3 py-1.5 transition ${mode === "queue" ? "bg-primary text-white" : "bg-white hover:bg-gray-50"}`}
              onClick={() => setMode("queue")}
            >
              {zh ? "推题队列" : "Queue"}
            </button>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            className="btn-primary px-4 py-2 rounded-lg text-sm disabled:opacity-40"
            disabled={busy}
            onClick={mode === "weak" ? loadWeak : loadQueue}
          >
            {mode === "queue" ? (zh ? "刷新队列" : "Refresh queue") : t("learnQuizLoad", lang)}
          </button>
          {mode === "queue" && (
            <button
              className="px-4 py-2 rounded-lg text-sm border border-gray-200 hover:bg-gray-50 disabled:opacity-40"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await rebuildPushQueue(studentId, 5);
                  setQuestions(await fetchPushQueue(studentId, 3));
                } finally {
                  setBusy(false);
                }
              }}
            >
              {zh ? "重建队列" : "Rebuild"}
            </button>
          )}
        </div>
      </div>

      {/* 统计 */}
      {Object.keys(results).length > 0 && (
        <div className="glass-card rounded-xl p-4 flex items-center gap-4 text-sm">
          <span className="text-green-600 font-semibold">✅ {correctCount}</span>
          <span className="text-amber-600 font-semibold">
            💪 {Object.keys(results).length - correctCount}
          </span>
          <span className="text-gray-400">·</span>
          <span className="text-gray-600">
            {zh ? "已答" : "Done"} {Object.keys(results).length}/{questions.length}
          </span>
        </div>
      )}

      {/* 题目列表 */}
      {questions.length > 0 ? (
        <div className="space-y-3">
          {questions.map((q, i) => {
            const res = results[q.question_id];
            const answered = !!res;
            return (
              <div
                key={q.question_id}
                className={`bg-white rounded-xl p-4 border shadow-sm transition ${
                  answered
                    ? res.is_correct
                      ? "border-green-200 bg-green-50/30"
                      : "border-amber-200 bg-amber-50/30"
                    : "border-gray-100"
                }`}
              >
                <div className="font-medium text-gray-800">
                  <span className="text-primary mr-1">{i + 1}.</span>
                  {q.prompt}
                </div>
                <p className="text-xs text-gray-400 mt-1">KP: {q.knowledge_point_id}</p>
                <div className="mt-3 flex gap-2">
                  <input
                    className="flex-1 max-w-xs px-3 py-2 rounded-lg border bg-white/70 disabled:bg-gray-50"
                    value={answers[q.question_id] || ""}
                    disabled={answered}
                    placeholder={t("correctAnswer", lang)}
                    onChange={(e) =>
                      setAnswers((a) => ({ ...a, [q.question_id]: e.target.value }))
                    }
                    onKeyDown={(e) => e.key === "Enter" && submitOne(q)}
                  />
                  {!answered && (
                    <button
                      className="btn-primary px-3 py-2 rounded-lg text-sm disabled:opacity-40"
                      disabled={busy || !answers[q.question_id]}
                      onClick={() => submitOne(q)}
                    >
                      {zh ? "提交" : "OK"}
                    </button>
                  )}
                </div>
                {res && (
                  <p
                    className={`mt-2 text-sm ${res.is_correct ? "text-green-600" : "text-amber-600"}`}
                  >
                    {res.is_correct ? "✅" : "💪"} {res.feedback}
                  </p>
                )}
              </div>
            );
          })}
          {Object.keys(results).length < questions.length && (
            <button
              className="btn-primary px-6 py-2.5 rounded-lg disabled:opacity-40"
              disabled={busy}
              onClick={submitAll}
            >
              {t("submit", lang)}
            </button>
          )}
          {Object.keys(results).length === questions.length && (
            <p className="text-center text-primary font-medium py-2 animate-fade-in">
              🎉 {zh ? "本轮完成！" : "Round done!"}
            </p>
          )}
        </div>
      ) : (
        !busy && (
          <div className="text-center py-16 text-gray-400">
            <div className="text-5xl mb-3">🎯</div>
            <p>{zh ? "点击上方按钮开始练习" : "Click the button above to start"}</p>
          </div>
        )
      )}
    </div>
  );
}
