import type { Health, Lang, ThemeName } from "../lib/types";
import { THEME_LIST, THEME_NAMES, t } from "../lib/i18n";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";

interface Props {
  lang: Lang;
  theme: ThemeName;
  studentId: string;
  health: Health | null;
  healthError: string | null;
  onLang: (l: Lang) => void;
  onTheme: (th: ThemeName) => void;
  onStudent: (s: string) => void;
}

export function Sidebar({
  lang,
  theme,
  studentId,
  health,
  healthError,
  onLang,
  onTheme,
  onStudent,
}: Props) {
  const online = health?.mode === "online";

  return (
    <Card className="w-72 shrink-0 shadow-xl flex flex-col gap-5 overflow-y-auto border-0">
      <CardHeader className="text-center pb-4 border-b border-black/5">
        <div className="text-3xl">🌟</div>
        <CardTitle className="text-primary mt-1">小博士</CardTitle>
        <p className="text-xs text-gray-500 mt-1">小学生 AI 学习助手</p>
      </CardHeader>

      <CardContent className="space-y-5 pt-0">
        <div className="text-sm">
        {healthError ? (
          <span className="inline-flex items-center gap-1.5 text-red-500">
            <span className="w-2 h-2 rounded-full bg-red-500" />
            {t("backendDown", lang)}
          </span>
        ) : (
          <span
            className={`inline-flex items-center gap-1.5 ${online ? "text-green-600" : "text-amber-600"}`}
          >
            <span className={`w-2 h-2 rounded-full ${online ? "bg-green-500" : "bg-amber-500"}`} />
            {online ? t("online", lang) : t("offline", lang)}
          </span>
        )}
        {health && (
          <div className="mt-2 space-y-1 text-xs text-gray-500">
            <div className="flex justify-between">
              <span>rag</span>
              <span className="font-mono">{health.rag_engine ?? health.vector_backend}</span>
            </div>
            <div className="flex justify-between">
              <span>memory</span>
              <span className="font-mono">{health.memory_backend}</span>
            </div>
            <div className="flex justify-between">
              <span>search</span>
              <span className="font-mono">
                {[health.tavily_enabled && "tavily", health.google_search_enabled && "google"]
                  .filter(Boolean)
                  .join("+") || "off"}
              </span>
            </div>
          </div>
        )}
      </div>

      <label className="block text-sm">
        <span className="text-gray-600">{t("student", lang)}</span>
        <Input
          className="mt-1.5 bg-white/70"
          value={studentId}
          onChange={(e) => onStudent(e.target.value)}
        />
      </label>

      {/* 语言 */}
      <label className="block text-sm">
        <span className="text-gray-600">{t("language", lang)}</span>
        <select
          className="mt-1.5 w-full px-3 py-2 rounded-lg border border-gray-300 text-sm bg-white/70 outline-none transition"
          value={lang}
          onChange={(e) => onLang(e.target.value as Lang)}
        >
          <option value="zh">中文</option>
          <option value="en">English</option>
        </select>
      </label>

      {/* 主题色卡网格 */}
      <div className="text-sm">
        <span className="text-gray-600">{t("theme", lang)}</span>
        <div className="mt-2 grid grid-cols-4 gap-2">
          {THEME_LIST.map((th) => (
            <button
              key={th}
              type="button"
              title={THEME_NAMES[th][lang]}
              onClick={() => onTheme(th)}
              className={`theme-swatch ${theme === th ? "active" : ""}`}
              style={{ background: THEME_NAMES[th].swatch }}
            />
          ))}
        </div>
        <p className="mt-2 text-xs text-gray-400 text-center">
          {THEME_NAMES[theme][lang]}
        </p>
      </div>
      </CardContent>
    </Card>
  );
}
