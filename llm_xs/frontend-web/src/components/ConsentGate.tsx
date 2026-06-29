import { useEffect, useState } from "react";
import { getConsentStatus, getPrivacyPolicy, recordConsent, type ConsentStatus, type PrivacyPolicy } from "../lib/api";
import { t } from "../lib/i18n";
import type { Lang } from "../lib/types";
import { Button } from "./ui/button";

type Props = {
  lang: Lang;
  studentId: string;
  onGranted: () => void;
};

export function ConsentGate({ lang, studentId, onGranted }: Props) {
  const [policy, setPolicy] = useState<PrivacyPolicy | null>(null);
  const [status, setStatus] = useState<ConsentStatus | null>(null);
  const [parentName, setParentName] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [p, s] = await Promise.all([getPrivacyPolicy(), getConsentStatus(studentId)]);
        if (cancelled) return;
        setPolicy(p);
        setStatus(s);
        if (s.valid) onGranted();
      } catch {
        if (!cancelled) setError(t("consentLoadError", lang));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [studentId, lang, onGranted]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!parentName.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      await recordConsent(studentId, parentName.trim());
      onGranted();
    } catch {
      setError(t("consentSubmitError", lang));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
        <div className="glass-card rounded-2xl p-8 max-w-lg w-full text-center">{t("consentLoading", lang)}</div>
      </div>
    );
  }

  if (!policy?.require_consent || status?.valid) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="glass-card rounded-2xl p-8 max-w-lg w-full shadow-2xl max-h-[90vh] overflow-y-auto">
        <h2 className="text-xl font-bold text-primary mb-2">{t("consentTitle", lang)}</h2>
        <p className="text-sm text-gray-600 mb-4">{policy?.summary}</p>
        <ul className="text-sm list-disc pl-5 mb-4 space-y-1 text-gray-700">
          {(policy?.data_collected ?? []).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <form onSubmit={handleSubmit} className="space-y-3">
          <label className="block text-sm font-medium">
            {t("consentParentName", lang)}
            <input
              className="mt-1 w-full rounded-lg border px-3 py-2"
              value={parentName}
              onChange={(e) => setParentName(e.target.value)}
              maxLength={64}
              required
            />
          </label>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? t("consentSubmitting", lang) : t("consentAgree", lang)}
          </Button>
        </form>
        <p className="text-xs text-gray-500 mt-4">{t("consentHint", lang)}</p>
      </div>
    </div>
  );
}
