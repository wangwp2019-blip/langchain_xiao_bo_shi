import { useState } from "react";
import { fetchKpWiki, searchWiki } from "../lib/learning-api";
import { t } from "../lib/i18n";
import type { Lang } from "../lib/types";

interface Props {
  lang: Lang;
  studentId: string;
}

interface WikiHit {
  unit_id: string;
  knowledge_point_id: string;
  title: string;
  snippet: string;
}

export function WikiPanel({ lang, studentId: _studentId }: Props) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<WikiHit[]>([]);
  const [active, setActive] = useState<{ kpId: string; content: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const zh = lang === "zh";

  const runSearch = async () => {
    const q = query.trim();
    if (!q) return;
    setBusy(true);
    setActive(null);
    try {
      const data = await searchWiki(q);
      setHits(data.hits);
    } finally {
      setBusy(false);
    }
  };

  const openKp = async (kpId: string) => {
    setBusy(true);
    try {
      const data = await fetchKpWiki(kpId);
      setActive({ kpId, content: data.content });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto p-6 space-y-5">
      <div className="glass-card rounded-xl p-4 space-y-3">
        <h2 className="font-bold text-primary">📖 {t("tabWiki", lang).replace(/^[^\s]+ /, "")}</h2>
        <div className="flex gap-2">
          <input
            className="flex-1 px-4 py-2.5 rounded-xl border bg-white focus:outline-none focus:border-primary/50"
            placeholder={t("wikiPlaceholder", lang)}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runSearch()}
          />
          <button
            className="btn-primary px-5 py-2 rounded-lg text-sm disabled:opacity-40"
            disabled={busy || !query.trim()}
            onClick={runSearch}
          >
            {t("wikiSearch", lang)}
          </button>
        </div>
      </div>

      {hits.length > 0 && !active && (
        <div className="space-y-2">
          {hits.map((h) => (
            <button
              key={h.knowledge_point_id}
              type="button"
              onClick={() => openKp(h.knowledge_point_id)}
              className="w-full text-left bg-white rounded-xl p-4 border border-gray-100 shadow-sm hover:border-primary/30 transition"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-800">{h.title}</span>
                <span className="text-xs text-gray-400">{h.unit_id}</span>
              </div>
              <p className="text-sm text-gray-500 mt-1 line-clamp-2">{h.snippet}</p>
            </button>
          ))}
        </div>
      )}

      {active && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-lg overflow-hidden animate-fade-in">
          <div className="bg-header text-white px-5 py-3 flex items-center justify-between">
            <h3 className="font-bold">{active.kpId}</h3>
            <button
              type="button"
              className="text-sm opacity-80 hover:opacity-100"
              onClick={() => setActive(null)}
            >
              ← {zh ? "返回" : "Back"}
            </button>
          </div>
          <div className="p-5 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
            {active.content}
          </div>
        </div>
      )}

      {hits.length === 0 && !active && !busy && (
        <div className="text-center py-16 text-gray-400">
          <div className="text-5xl mb-3">📖</div>
          <p>{t("wikiEmpty", lang)}</p>
        </div>
      )}
    </div>
  );
}
