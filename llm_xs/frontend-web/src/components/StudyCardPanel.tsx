import { useState } from "react";
import { generateStudyCard, speakText } from "../lib/learning-api";
import { t } from "../lib/i18n";
import type { Lang } from "../lib/types";
import type { StudyCard } from "../lib/learning-types";

interface Props {
  lang: Lang;
}

export function StudyCardPanel({ lang }: Props) {
  const [question, setQuestion] = useState("");
  const [card, setCard] = useState<StudyCard | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const generate = async () => {
    const q = question.trim();
    if (!q || busy) return;
    setBusy(true);
    setError("");
    setCard(null);
    try {
      const data = await generateStudyCard(q);
      setCard(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto p-6 space-y-5">
      <div className="glass-card rounded-xl p-4 space-y-3">
        <h2 className="font-bold text-primary">{t("cardTitle", lang)}</h2>
        <input
          className="w-full px-4 py-3 rounded-xl border bg-white"
          placeholder={t("cardPlaceholder", lang)}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && generate()}
        />
        <button
          className="btn-primary px-6 py-2 rounded-lg disabled:opacity-40"
          disabled={busy}
          onClick={generate}
        >
          {busy ? "…" : t("cardGenerate", lang)}
        </button>
        {error && <p className="text-sm text-red-500">{error}</p>}
      </div>

      {card && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-lg overflow-hidden animate-fade-in">
          <div className="bg-header text-white px-5 py-4 flex justify-between items-center">
            <h3 className="font-bold">{card.topic}</h3>
            <button
              type="button"
              className="text-lg opacity-80 hover:opacity-100"
              onClick={() => speakText(card.answer, lang)}
              title={t("speak", lang)}
            >
              🔊
            </button>
          </div>
          <div className="p-5 space-y-4 text-sm">
            <p className="text-gray-700 leading-relaxed">{card.answer}</p>
            {card.knowledge_points?.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-gray-400 mb-1">{t("cardKp", lang)}</div>
                <div className="flex flex-wrap gap-1">
                  {card.knowledge_points.map((kp) => (
                    <span key={kp} className="px-2 py-0.5 rounded bg-primary/10 text-primary text-xs">
                      {kp}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {card.example && (
              <div className="bg-amber-50 rounded-lg p-3 text-amber-900">
                <span className="text-xs font-semibold">💡 </span>
                {card.example}
              </div>
            )}
            {card.encouragement && (
              <p className="text-primary font-medium text-center pt-2">{card.encouragement}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
