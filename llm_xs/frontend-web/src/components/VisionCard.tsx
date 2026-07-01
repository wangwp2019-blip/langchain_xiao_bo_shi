import type { VisionUnderstandResponse } from "../lib/learning-types";
import type { Lang } from "../lib/types";

interface Props {
  lang: Lang;
  vision: VisionUnderstandResponse;
  onAsk: (question: string) => void;
  onSaveLearning: () => void;
  onDismiss: () => void;
}

export function VisionCard({ lang, vision, onAsk, onSaveLearning, onDismiss }: Props) {
  const zh = lang === "zh";
  return (
    <div className="mx-5 mb-3 p-4 rounded-xl border border-primary/30 bg-primary/5 shadow-sm animate-fade-in">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div>
          <p className="text-sm font-semibold text-primary">
            📷 {zh ? "拍照识别" : "Photo scan"}
          </p>
          <p className="text-xs text-gray-600 mt-0.5">{vision.summary}</p>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          className="text-gray-400 hover:text-gray-600 text-sm"
        >
          ✕
        </button>
      </div>
      <ul className="text-sm space-y-1 mb-3 max-h-32 overflow-y-auto">
        {vision.items.map((it) => (
          <li key={it.index} className="flex gap-2 text-gray-700">
            <span className="shrink-0 w-5">
              {it.is_correct === true ? "✓" : it.is_correct === false ? "✗" : "·"}
            </span>
            <span className="truncate">{it.prompt}</span>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="text-xs px-3 py-1.5 rounded-full bg-white border border-primary/40 text-primary hover:bg-primary/10"
          onClick={() => onAsk(zh ? "帮我讲讲错题" : "Explain my mistakes")}
        >
          {zh ? "讲解错题" : "Explain mistakes"}
        </button>
        <button
          type="button"
          className="text-xs px-3 py-1.5 rounded-full bg-white border border-gray-200 hover:border-primary/40"
          onClick={() => onAsk(zh ? "这页作业怎么样？" : "How did I do?")}
        >
          {zh ? "问问小博士" : "Ask Jarvis"}
        </button>
        <button
          type="button"
          className="text-xs px-3 py-1.5 rounded-full btn-primary"
          onClick={onSaveLearning}
        >
          {zh ? "记入学情" : "Save to profile"}
        </button>
      </div>
    </div>
  );
}
