import { useState } from "react";
import { createQuiz, gradeQuiz } from "../lib/api";
import { GRADES, SUBJECTS, t } from "../lib/i18n";
import type { GradeResult, Lang, QuizPublic } from "../lib/types";

interface Props {
  lang: Lang;
}

export function QuizPanel({ lang }: Props) {
  const [grade, setGrade] = useState(GRADES[2]);
  const [subject, setSubject] = useState(SUBJECTS[0]);
  const [count, setCount] = useState(10);
  const [quiz, setQuiz] = useState<QuizPublic | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<GradeResult | null>(null);
  const [busy, setBusy] = useState(false);

  const onNewQuiz = async () => {
    setBusy(true);
    setResult(null);
    setAnswers({});
    try {
      const data = await createQuiz(grade, subject, count);
      setQuiz(data.public);
      setSessionId(data.session_id);
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = async () => {
    if (!quiz || !sessionId) return;
    setBusy(true);
    try {
      setResult(await gradeQuiz(sessionId, answers));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto p-5 space-y-5">
      {/* 出题控制栏 */}
      <div className="glass-card rounded-xl p-4 shadow-sm">
        <div className="flex flex-wrap gap-4 items-end">
          <label className="text-sm">
            <span className="text-gray-600">{t("grade", lang)}</span>
            <select
              className="mt-1.5 block px-3 py-2 rounded-lg border border-gray-300 bg-white/70 outline-none transition"
              value={grade}
              onChange={(e) => setGrade(e.target.value)}
            >
              {GRADES.map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="text-gray-600">{t("subject", lang)}</span>
            <select
              className="mt-1.5 block px-3 py-2 rounded-lg border border-gray-300 bg-white/70 outline-none transition"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            >
              {SUBJECTS.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="text-gray-600">{t("count", lang)}</span>
            <input
              type="number"
              min={1}
              max={20}
              className="mt-1.5 block w-20 px-3 py-2 rounded-lg border border-gray-300 bg-white/70 outline-none transition"
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
            />
          </label>
          <button
            className="btn-primary px-6 py-2.5 rounded-lg font-medium disabled:opacity-40"
            disabled={busy}
            onClick={onNewQuiz}
          >
            {t("newQuiz", lang)}
          </button>
        </div>
      </div>

      {/* 判分结果 */}
      {result && (
        <div className="bg-header text-white rounded-xl p-5 shadow-md animate-fade-in">
          <div className="text-2xl font-bold">
            {t("score", lang)}: {result.score}/100
            <span className="text-base font-normal opacity-90 ml-3">
              （{result.correct}/{result.total}）
            </span>
          </div>
          <p className="opacity-90 mt-2">{result.summary}</p>
        </div>
      )}

      {/* 题目列表 */}
      {quiz && (
        <div className="space-y-3">
          {quiz.questions.map((q) => {
            const item = result?.items.find((it) => it.index === q.index);
            return (
              <div
                key={q.index}
                className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm animate-fade-in"
              >
                <div className="font-medium text-gray-800">
                  <span className="text-primary mr-1">第 {q.index} 题</span>
                  {q.prompt}
                </div>
                <input
                  className="mt-3 w-48 px-3 py-2 rounded-lg border border-gray-300 bg-white/70 outline-none transition disabled:bg-gray-50"
                  value={answers[String(q.index)] || ""}
                  disabled={!!result}
                  placeholder={t("correctAnswer", lang)}
                  onChange={(e) =>
                    setAnswers((a) => ({ ...a, [String(q.index)]: e.target.value }))
                  }
                />
                {item && (
                  <div className="mt-3 text-sm flex items-start gap-2">
                    <span className="text-lg">{item.is_correct ? "✅" : "💪"}</span>
                    <div>
                      <span>{item.feedback}</span>
                      {!item.is_correct && (
                        <div className="text-gray-500 mt-1">
                          {t("correctAnswer", lang)}:{" "}
                          <span className="font-medium text-gray-700">
                            {item.correct_answer}
                          </span>
                          <span className="ml-2">{item.explanation}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
          {!result && (
            <button
              className="btn-primary px-7 py-2.5 rounded-lg font-medium disabled:opacity-40"
              disabled={busy}
              onClick={onSubmit}
            >
              {t("submit", lang)}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
