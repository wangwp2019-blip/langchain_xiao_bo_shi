import { useEffect, useState } from "react";
import { fetchKpCatalog, fetchProfile, submitOnboarding } from "../lib/learning-api";
import { GRADES, SUBJECTS, t } from "../lib/i18n";
import type { Lang } from "../lib/types";
import type { UnitCatalogEntry } from "../lib/learning-types";
import { Button } from "./ui/button";

interface Props {
  lang: Lang;
  studentId: string;
  onDone: () => void;
}

export function OnboardingWizard({ lang, studentId, onDone }: Props) {
  const [grade, setGrade] = useState(GRADES[1]);
  const [subject, setSubject] = useState(SUBJECTS[0]);
  const [unitId, setUnitId] = useState("");
  const [selfAssessment, setSelfAssessment] = useState("一般");
  const [units, setUnits] = useState<UnitCatalogEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    fetchProfile(studentId)
      .then((p) => {
        if (p) onDone();
      })
      .catch(() => {
        /* 无 profile 或网络错误 → 显示向导 */
      })
      .finally(() => setChecking(false));
  }, [studentId, onDone]);

  useEffect(() => {
    const level = parseInt(grade.replace(/\D/g, "") || "2", 10);
    fetchKpCatalog(level)
      .then(setUnits)
      .catch(() => setUnits([]));
  }, [grade]);

  const submit = async () => {
    setBusy(true);
    try {
      await submitOnboarding(studentId, grade, subject, unitId || undefined, selfAssessment);
      onDone();
    } finally {
      setBusy(false);
    }
  };

  if (checking) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
        <div className="glass-card rounded-2xl p-8">加载中…</div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="glass-card rounded-2xl p-8 max-w-md w-full shadow-2xl">
        <div className="text-center mb-6">
          <div className="text-4xl mb-2">🎒</div>
          <h2 className="text-xl font-bold text-primary">{t("onboardingTitle", lang)}</h2>
          <p className="text-sm text-gray-500 mt-1">{t("onboardingHint", lang)}</p>
        </div>
        <div className="space-y-4">
          <label className="block text-sm">
            <span className="text-gray-600">{t("grade", lang)}</span>
            <select
              className="mt-1 w-full rounded-lg border px-3 py-2 bg-white"
              value={grade}
              onChange={(e) => setGrade(e.target.value)}
            >
              {GRADES.map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">{t("subject", lang)}</span>
            <select
              className="mt-1 w-full rounded-lg border px-3 py-2 bg-white"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            >
              {SUBJECTS.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">{t("onboardingUnit", lang)}</span>
            <select
              className="mt-1 w-full rounded-lg border px-3 py-2 bg-white"
              value={unitId}
              onChange={(e) => setUnitId(e.target.value)}
            >
              <option value="">{t("onboardingUnitAuto", lang)}</option>
              {units.map((u) => (
                <option key={u.unit_id} value={u.unit_id}>
                  {u.unit_title}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">{t("onboardingSelf", lang)}</span>
            <select
              className="mt-1 w-full rounded-lg border px-3 py-2 bg-white"
              value={selfAssessment}
              onChange={(e) => setSelfAssessment(e.target.value)}
            >
              {["很好", "一般", "需加强"].map((o) => (
                <option key={o}>{o}</option>
              ))}
            </select>
          </label>
          <Button className="w-full" disabled={busy} onClick={submit}>
            {busy ? "…" : t("onboardingStart", lang)}
          </Button>
        </div>
      </div>
    </div>
  );
}
