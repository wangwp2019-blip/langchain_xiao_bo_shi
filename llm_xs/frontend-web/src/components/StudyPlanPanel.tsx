import { useState } from "react";
import { createStudyPlan } from "../lib/learning-api";
import { t } from "../lib/i18n";
import type { Lang } from "../lib/types";
import type { StudyPlan } from "../lib/learning-types";

interface Props {
  lang: Lang;
  studentId: string;
}

export function StudyPlanPanel({ lang, studentId }: Props) {
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [busy, setBusy] = useState(false);
  const [doneSteps, setDoneSteps] = useState<Set<number>>(new Set());

  const generate = async () => {
    setBusy(true);
    setDoneSteps(new Set());
    try {
      setPlan(await createStudyPlan(studentId));
    } finally {
      setBusy(false);
    }
  };

  const toggleStep = (n: number) => {
    setDoneSteps((s) => {
      const next = new Set(s);
      if (next.has(n)) next.delete(n);
      else next.add(n);
      return next;
    });
  };

  return (
    <div className="h-full overflow-y-auto p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-primary">{t("planTitle", lang)}</h2>
          <p className="text-sm text-gray-500">{t("planSubtitle", lang)}</p>
        </div>
        <button
          className="btn-primary px-5 py-2 rounded-lg text-sm font-medium disabled:opacity-40"
          disabled={busy}
          onClick={generate}
        >
          {busy ? "…" : t("planGenerate", lang)}
        </button>
      </div>

      {!plan && (
        <div className="text-center py-16 text-gray-400">
          <div className="text-5xl mb-3">📋</div>
          <p>{t("planEmpty", lang)}</p>
        </div>
      )}

      {plan && (
        <div className="space-y-3">
          <p className="text-sm text-gray-600">
            {plan.title} · ~{plan.total_minutes} {t("minutes", lang)}
          </p>
          {plan.steps.map((step) => {
            const done = doneSteps.has(step.step);
            return (
              <button
                key={step.step}
                type="button"
                onClick={() => toggleStep(step.step)}
                className={`w-full text-left rounded-xl p-4 border transition ${
                  done
                    ? "bg-green-50 border-green-200 opacity-75"
                    : "bg-white border-gray-100 shadow-sm hover:border-primary/30"
                }`}
              >
                <div className="flex items-start gap-3">
                  <span
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0 ${
                      done ? "bg-green-500 text-white" : "bg-primary/10 text-primary"
                    }`}
                  >
                    {done ? "✓" : step.step}
                  </span>
                  <div>
                    <div className={`font-medium ${done ? "line-through text-gray-500" : "text-gray-800"}`}>
                      {step.title}
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      ~{step.duration_min} {t("minutes", lang)}
                    </div>
                  </div>
                </div>
              </button>
            );
          })}
          {doneSteps.size === plan.steps.length && (
            <p className="text-center text-green-600 font-medium py-4 animate-fade-in">
              🎉 {t("planComplete", lang)}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
