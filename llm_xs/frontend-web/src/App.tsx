import { useCallback, useEffect, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { ChatPanel } from "./components/ChatPanel";
import { QuizPanel } from "./components/QuizPanel";
import { ConsentGate } from "./components/ConsentGate";
import { OnboardingWizard } from "./components/OnboardingWizard";
import { ProgressPanel } from "./components/ProgressPanel";
import { StudyPlanPanel } from "./components/StudyPlanPanel";
import { LearningQuizPanel } from "./components/LearningQuizPanel";
import { StudyCardPanel } from "./components/StudyCardPanel";
import { ParentDashboard } from "./components/ParentDashboard";
import { WikiPanel } from "./components/WikiPanel";
import { useHealth } from "./hooks/useHealth";
import { t } from "./lib/i18n";
import type { AppMode, AppTab } from "./lib/learning-types";
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

const STUDENT_TABS: { key: AppTab; labelKey: string }[] = [
  { key: "chat", labelKey: "tabChat" },
  { key: "learn", labelKey: "tabLearn" },
  { key: "quiz", labelKey: "tabQuiz" },
  { key: "progress", labelKey: "tabProgress" },
  { key: "plan", labelKey: "tabPlan" },
  { key: "wiki", labelKey: "tabWiki" },
  { key: "card", labelKey: "tabCard" },
];

export default function App() {
  const [lang, setLang] = useState<Lang>("zh");
  const [theme, setTheme] = useState<ThemeName>("ocean");
  const [tab, setTab] = useState<AppTab>("chat");
  const [mode, setMode] = useState<AppMode>("student");
  const [authReady, setAuthReady] = useState(false);
  const [consentOk, setConsentOk] = useState(true);
  const [onboardOk, setOnboardOk] = useState(false);
  const [authUser, setAuthUserState] = useState(getAuthUser());
  const { health, error } = useHealth();

  const studentId = authUser?.id || "web-kid";
  const onConsentGranted = useCallback(() => setConsentOk(true), []);
  const onOnboardDone = useCallback(() => setOnboardOk(true), []);

  useEffect(() => {
    const hashToken = consumeHashToken();
    if (hashToken) setToken(hashToken);
    if (!isTokenValid()) {
      redirectToLogin();
      return;
    }
    syncAuthUser().finally(() => {
      setAuthUserState(getAuthUser());
      setAuthReady(true);
    });
  }, []);

  useEffect(() => {
    if (!authReady) return;
    const interval = setInterval(async () => {
      if (isTokenExpiringSoon() && !(await refreshToken())) redirectToLogin();
    }, 120_000);
    return () => clearInterval(interval);
  }, [authReady]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    if (health?.require_parent_consent) setConsentOk(false);
    if (health?.simple_chat_mode) {
      setConsentOk(true);
      setOnboardOk(true);
    }
  }, [health?.require_parent_consent, health?.simple_chat_mode]);

  const simpleChat = health?.simple_chat_mode ?? false;
  const studentTabs = simpleChat
    ? [{ key: "chat" as AppTab, labelKey: "tabChat" }]
    : STUDENT_TABS;

  if (!authReady) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl mb-3">🌟</div>
          <p className="text-gray-500">{t("loading", lang)}</p>
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
      {consentOk && !onboardOk && mode === "student" && !simpleChat && (
        <OnboardingWizard lang={lang} studentId={studentId} onDone={onOnboardDone} />
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

      <main className="flex-1 glass-card rounded-2xl shadow-xl flex flex-col overflow-hidden min-w-0">
        <header className="bg-header text-white px-6 py-4 flex items-center justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-lg font-bold tracking-wide truncate">{t("appTitle", lang)}</h1>
            <p className="text-xs opacity-90 mt-0.5 truncate">{t("subtitle", lang)}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <div className="flex rounded-lg overflow-hidden bg-white/15 text-sm">
              <button
                className={`px-3 py-1.5 transition ${mode === "student" ? "bg-white/25" : "hover:bg-white/10"}`}
                onClick={() => setMode("student")}
              >
                {t("modeStudent", lang)}
              </button>
              <button
                className={`px-3 py-1.5 transition ${mode === "parent" ? "bg-white/25" : "hover:bg-white/10"}`}
                onClick={() => setMode("parent")}
              >
                {t("modeParent", lang)}
              </button>
            </div>
            <span className="text-xs opacity-90 hidden sm:inline">
              👋 {authUser?.display_name || "小朋友"}
            </span>
            <button
              onClick={handleLogout}
              className="px-2.5 py-1 rounded-lg text-xs bg-white/20 hover:bg-white/30"
            >
              {t("logout", lang)}
            </button>
          </div>
        </header>

        {mode === "parent" ? (
          <div className="flex-1 min-h-0 bg-white/60">
            <ParentDashboard lang={lang} studentId={studentId} />
          </div>
        ) : (
          <>
            <nav className="flex gap-0.5 px-3 pt-2 bg-white/40 overflow-x-auto">
              {studentTabs.map(({ key, labelKey }) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`px-3 py-2 rounded-t-lg text-xs sm:text-sm font-medium whitespace-nowrap transition ${
                    tab === key
                      ? "bg-white text-primary shadow-sm"
                      : "text-gray-500 hover:text-gray-700"
                  }`}
                >
                  {t(labelKey as Parameters<typeof t>[0], lang)}
                </button>
              ))}
            </nav>
            <div className="flex-1 min-h-0 bg-white/60">
              {tab === "chat" && (
                <ChatPanel lang={lang} studentId={studentId} simpleChat={simpleChat} />
              )}
              {tab === "quiz" && <QuizPanel lang={lang} />}
              {tab === "learn" && <LearningQuizPanel lang={lang} studentId={studentId} />}
              {tab === "progress" && <ProgressPanel lang={lang} studentId={studentId} />}
              {tab === "plan" && <StudyPlanPanel lang={lang} studentId={studentId} />}
              {tab === "wiki" && <WikiPanel lang={lang} studentId={studentId} />}
              {tab === "card" && <StudyCardPanel lang={lang} />}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
