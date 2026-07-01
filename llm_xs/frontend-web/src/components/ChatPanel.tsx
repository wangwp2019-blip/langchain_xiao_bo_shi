import { useEffect, useRef, useState } from "react";
import { chatStream, fetchPromptSuggestions, type SuggestedPrompt } from "../lib/api";
import { classifyPhoto, speakText, startVoiceInput, visionUnderstand } from "../lib/learning-api";
import { t } from "../lib/i18n";
import type { Lang } from "../lib/types";
import type { VisionUnderstandResponse } from "../lib/learning-types";
import { VisionCard } from "./VisionCard";

interface Msg {
  role: "user" | "bot";
  text: string;
}

interface Props {
  lang: Lang;
  studentId: string;
  simpleChat?: boolean;
}

const FALLBACK_PROMPTS: Record<Lang, SuggestedPrompt[]> = {
  zh: [
    { text: "RAG 是什么？", category: "知识库" },
    { text: "125 + 38 等于多少？", category: "数学" },
    { text: "今天几号？星期几？", category: "生活" },
  ],
  en: [
    { text: "What is RAG?", category: "Knowledge" },
    { text: "What is 125 + 38?", category: "Math" },
    { text: "What is today's date?", category: "Daily" },
  ],
};

export function ChatPanel({ lang, studentId, simpleChat = false }: Props) {
  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "bot",
      text:
        lang === "zh"
          ? "你好！我是小博士，可以聊天并检索知识库。直接提问，我会先查资料再回答。"
          : "Hi! Ask me anything — I'll search the knowledge base first when helpful.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [vision, setVision] = useState<VisionUnderstandResponse | null>(null);
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

  const send = async (text?: string, visionId?: string | null) => {
    const question = (text ?? input).trim();
    if (!question || busy) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text: question }, { role: "bot", text: "" }]);
    scrollToBottom();

    const vid = visionId ?? vision?.vision_id ?? null;
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
      }, vid);
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

  const toggleVoice = () => {
    if (listening) {
      setListening(false);
      return;
    }
    setListening(true);
    const stop = startVoiceInput((text) => {
      setInput(text);
      setListening(false);
      stop();
    }, lang);
    setTimeout(() => {
      setListening(false);
      stop();
    }, 8000);
  };

  const handlePhoto = () => {
    const text = window.prompt(
      lang === "zh"
        ? "粘贴拍照/OCR 识别的文字（或描述题目）："
        : "Paste OCR text or describe the homework:",
    );
    if (!text?.trim()) return;
    visionUnderstand(studentId, text.trim(), "homework")
      .then((v) => {
        setVision(v);
        setMessages((m) => [
          ...m,
          {
            role: "bot",
            text:
              lang === "zh"
                ? `📷 识别完成：${v.summary}。你可以点下方卡片提问，或「记入学情」。`
                : `📷 Scan done: ${v.summary}. Use the card below to ask or save.`,
          },
        ]);
        scrollToBottom();
      })
      .catch(() => {});
  };

  const handleSaveLearning = () => {
    if (!vision) return;
    const text = vision.items.map((i) => i.prompt).join("\n");
    classifyPhoto(studentId, text)
      .then((r) => {
        const msg =
          r.triage === "auto"
            ? lang === "zh"
              ? "✅ 已自动归类并记录学情！"
              : "✅ Saved to learning profile!"
            : lang === "zh"
              ? "📋 已提交家长确认队列。"
              : "📋 Sent to parent confirm queue.";
        setMessages((m) => [...m, { role: "bot", text: msg }]);
      })
      .catch(() => {});
  };

  const speakLastBot = () => {
    const last = [...messages].reverse().find((m) => m.role === "bot" && m.text);
    if (last) speakText(last.text, lang);
  };

  return (
    <div className="flex flex-col h-full">
      {vision && !simpleChat && (
        <VisionCard
          lang={lang}
          vision={vision}
          onAsk={(q) => send(q, vision.vision_id)}
          onSaveLearning={handleSaveLearning}
          onDismiss={() => setVision(null)}
        />
      )}

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-4">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex items-start gap-2.5 animate-fade-in ${
              m.role === "user" ? "flex-row-reverse" : "flex-row"
            }`}
          >
            <div
              className={`w-9 h-9 shrink-0 rounded-full flex items-center justify-center text-lg ${
                m.role === "user" ? "bg-gray-200" : "bg-header"
              }`}
            >
              {m.role === "user" ? "🧒" : "🌟"}
            </div>
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

      <div className="p-4 border-t border-black/5 flex gap-2 bg-white/50 items-center">
        <button
          type="button"
          className={`p-2.5 rounded-xl border transition ${listening ? "border-primary bg-primary/10" : "border-gray-200 hover:border-primary/40"}`}
          onClick={toggleVoice}
          title={t("voiceInput", lang)}
        >
          🎤
        </button>
        {!simpleChat && (
          <button
            type="button"
            className="p-2.5 rounded-xl border border-gray-200 hover:border-primary/40 transition"
            onClick={handlePhoto}
            title={t("photoInput", lang)}
          >
            📷
          </button>
        )}
        <button
          type="button"
          className="p-2.5 rounded-xl border border-gray-200 hover:border-primary/40 transition"
          onClick={speakLastBot}
          title={t("speak", lang)}
        >
          🔊
        </button>
        <input
          className="flex-1 px-4 py-3 rounded-xl border border-gray-300 bg-white outline-none transition"
          placeholder={t("inputPlaceholder", lang)}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button
          className="btn-primary px-5 rounded-xl font-medium disabled:opacity-40 shrink-0"
          disabled={busy}
          onClick={() => send()}
        >
          {busy ? "..." : t("send", lang)}
        </button>
      </div>
    </div>
  );
}
