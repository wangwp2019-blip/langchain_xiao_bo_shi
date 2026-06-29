import { useEffect, useRef, useState } from "react";
import { chatStream, fetchPromptSuggestions, type SuggestedPrompt } from "../lib/api";
import { t } from "../lib/i18n";
import type { Lang } from "../lib/types";

interface Msg {
  role: "user" | "bot";
  text: string;
}

interface Props {
  lang: Lang;
  studentId: string;
}

const FALLBACK_PROMPTS: Record<Lang, SuggestedPrompt[]> = {
  zh: [
    { text: "太阳系有几大行星？", category: "科学" },
    { text: "125 + 38 等于多少？", category: "数学" },
    { text: "为什么要系安全带？", category: "安全" },
  ],
  en: [
    { text: "How many planets are in the solar system?", category: "Science" },
    { text: "What is 125 + 38?", category: "Math" },
    { text: "Why should we wear seat belts?", category: "Safety" },
  ],
};

export function ChatPanel({ lang, studentId }: Props) {
  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "bot",
      text:
        lang === "zh"
          ? '你好呀！我是小博士，可以陪你一起学习。试着问我："太阳系有几大行星？"吧！'
          : "Hi! I'm Dr. Kid. Try asking: 'How many planets are in the solar system?'",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [suggestions, setSuggestions] = useState<SuggestedPrompt[]>(FALLBACK_PROMPTS[lang]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    fetchPromptSuggestions(lang)
      .then((items) => {
        if (!cancelled && items.length > 0) setSuggestions(items);
      })
      .catch(() => {
        if (!cancelled) setSuggestions(FALLBACK_PROMPTS[lang]);
      });
    return () => {
      cancelled = true;
    };
  }, [lang]);

  const scrollToBottom = () => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    });
  };

  const send = async (text?: string) => {
    const question = (text ?? input).trim();
    if (!question || busy) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text: question }, { role: "bot", text: "" }]);
    scrollToBottom();

    try {
      await chatStream(question, studentId, studentId, (chunk) => {
        setMessages((m) => {
          const next = [...m];
          next[next.length - 1] = {
            role: "bot",
            text: next[next.length - 1].text + chunk,
          };
          return next;
        });
        scrollToBottom();
      });
    } catch (e) {
      setMessages((m) => {
        const next = [...m];
        next[next.length - 1] = { role: "bot", text: "哎呀，连接出错了：" + String(e) };
        return next;
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* 消息区 */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-4">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex items-start gap-2.5 animate-fade-in ${
              m.role === "user" ? "flex-row-reverse" : "flex-row"
            }`}
          >
            {/* 头像 */}
            <div
              className={`w-9 h-9 shrink-0 rounded-full flex items-center justify-center text-lg ${
                m.role === "user" ? "bg-gray-200" : "bg-header"
              }`}
            >
              {m.role === "user" ? "🧒" : "🌟"}
            </div>
            {/* 气泡 */}
            <div
              className={`max-w-[78%] px-4 py-3 rounded-2xl whitespace-pre-wrap break-words text-[15px] leading-relaxed shadow-sm ${
                m.role === "user"
                  ? "btn-primary rounded-tr-sm"
                  : "bg-white text-gray-800 border border-gray-100 rounded-tl-sm"
              }`}
            >
              {m.text || "…"}
            </div>
          </div>
        ))}
      </div>

      {/* 快捷提问 */}
      {suggestions.length > 0 && (
        <div className="px-4 pb-2 bg-white/50 border-t border-black/5">
          <p className="text-xs text-gray-500 mb-2 pt-2">{t("promptSuggestions", lang)}</p>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((item) => (
              <button
                key={item.text}
                type="button"
                disabled={busy}
                onClick={() => send(item.text)}
                className="text-xs px-3 py-1.5 rounded-full bg-white border border-gray-200 text-gray-700 hover:border-primary hover:text-primary transition disabled:opacity-40"
                title={item.category}
              >
                {item.text}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 输入区 */}
      <div className="p-4 border-t border-black/5 flex gap-2.5 bg-white/50">
        <input
          className="flex-1 px-4 py-3 rounded-xl border border-gray-300 bg-white outline-none transition"
          placeholder={t("inputPlaceholder", lang)}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button
          className="btn-primary px-7 rounded-xl font-medium disabled:opacity-40"
          disabled={busy}
          onClick={() => send()}
        >
          {busy ? "..." : t("send", lang)}
        </button>
      </div>
    </div>
  );
}
