import { useEffect, useState, useCallback } from "react";
import { Sidebar } from "./components/Sidebar";
import { ChatPanel } from "./components/ChatPanel";
import { QuizPanel } from "./components/QuizPanel";
import { ConsentGate } from "./components/ConsentGate";
import { useHealth } from "./hooks/useHealth";
import { t } from "./lib/i18n";
import type { Lang, ThemeName } from "./lib/types";
import {
  consumeHashToken,
  clearAuth,
  getAuthUser,
  isTokenExpiringSoon,
  isTokenValid,
  redirectToLogin,
  refreshToken,
  setToken,
  syncAuthUser,
} from "./lib/api";

export default function App() {
  const [lang, setLang] = useState<Lang>("zh");
  const [theme, setTheme] = useState<ThemeName>("ocean");
  const [tab, setTab] = useState<"chat" | "quiz">("chat");
  const [authReady, setAuthReady] = useState(false);
  const [consentOk, setConsentOk] = useState(true);
  const [authUser, setAuthUserState] = useState(getAuthUser());
  const { health, error } = useHealth();

  const studentId = authUser?.id || "web-kid";
  const onConsentGranted = useCallback(() => setConsentOk(true), []);

  // ---------- 登录守卫 + token 初始化 ----------
  useEffect(() => {
    // 1) 从 URL hash 读取登录跳转带来的 token
    const hashToken = consumeHashToken();
    if (hashToken) {
      setToken(hashToken);
    }

    // 2) 检查 token 是否有效
    if (!isTokenValid()) {
      redirectToLogin();
      return; // 跳转中，不渲染
    }

    // 3) 回填真实用户身份（修复 studentId 长期为 web-kid 导致的记忆/展示问题）
    syncAuthUser().finally(() => {
      setAuthUserState(getAuthUser());
      setAuthReady(true);
    });
  }, []);

  // ---------- 自动续期（每 2 分钟检查一次）----------
  useEffect(() => {
    if (!authReady) return;
    const interval = setInterval(async () => {
      if (isTokenExpiringSoon()) {
        const ok = await refreshToken();
        if (!ok) {
          // 续期失败 → 跳转登录
          redirectToLogin();
        }
      }
    }, 2 * 60 * 1000); // 2 分钟
    return () => clearInterval(interval);
  }, [authReady]);

  // ---------- 页面可见时也检查一次（从后台切回）----------
  useEffect(() => {
    if (!authReady) return;
    const onVisible = () => {
      if (document.visibilityState === "visible" && !isTokenValid()) {
        redirectToLogin();
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [authReady]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    if (health?.require_parent_consent) {
      setConsentOk(false);
    }
  }, [health?.require_parent_consent]);

  // 登录守卫：未验证前显示加载中
  if (!authReady) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl mb-3">🌟</div>
          <p className="text-gray-500">正在验证登录...</p>
        </div>
      </div>
    );
  }

  const handleLogout = () => {
    clearAuth();
    redirectToLogin();
  };

  return (
    <div className="h-full flex items-stretch gap-5 p-5 max-w-7xl mx-auto">
      {!consentOk && health?.require_parent_consent && (
        <ConsentGate lang={lang} studentId={studentId} onGranted={onConsentGranted} />
      )}
      <Sidebar
        lang={lang}
        theme={theme}
        studentId={studentId}
        health={health}
        healthError={error}
        onLang={setLang}
        onTheme={setTheme}
        onStudent={() => {}}
      />

      <main className="flex-1 glass-card rounded-2xl shadow-xl flex flex-col overflow-hidden">
        {/* 顶部标题栏 + 用户信息 */}
        <header className="bg-header text-white px-7 py-5 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-wide">{t("appTitle", lang)}</h1>
            <p className="text-sm opacity-90 mt-1">{t("subtitle", lang)}</p>
          </div>
          {/* 用户信息 + 登出 */}
          <div className="flex items-center gap-3">
            <span className="text-sm opacity-90">
              👋 {authUser?.display_name || authUser?.email || "小朋友"}
            </span>
            <button
              onClick={handleLogout}
              className="px-3 py-1.5 rounded-lg text-sm bg-white/20 hover:bg-white/30 transition"
            >
              退出
            </button>
          </div>
        </header>

        {/* Tab 导航 */}
        <nav className="flex gap-1 px-5 pt-3 bg-white/40">
          {(["chat", "quiz"] as const).map((key) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-5 py-2.5 rounded-t-xl text-sm font-medium transition-all ${
                tab === key
                  ? "bg-white text-primary shadow-sm"
                  : "text-gray-500 hover:text-gray-700 hover:bg-white/50"
              }`}
            >
              {key === "chat" ? t("tabChat", lang) : t("tabQuiz", lang)}
            </button>
          ))}
        </nav>

        {/* 内容区 */}
        <div className="flex-1 min-h-0 bg-white/60">
          {tab === "chat" ? (
            <ChatPanel lang={lang} studentId={studentId} />
          ) : (
            <QuizPanel lang={lang} />
          )}
        </div>
      </main>
    </div>
  );
}
