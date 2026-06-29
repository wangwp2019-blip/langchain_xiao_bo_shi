import type { Lang, ThemeName } from "./types";

type Dict = Record<string, { zh: string; en: string }>;

const STRINGS: Dict = {
  appTitle: { zh: "小博士 AI 学习伙伴", en: "Dr. Kid AI Buddy" },
  subtitle: {
    zh: "语文 · 数学 · 科学 · 安全 · 健康 —— 有问题就问我吧！",
    en: "Chinese · Math · Science · Safety · Health — ask me anything!",
  },
  tabChat: { zh: "💬 问答", en: "💬 Chat" },
  tabQuiz: { zh: "📝 出题练习", en: "📝 Quiz" },
  inputPlaceholder: { zh: "在这里输入你的问题...", en: "Type your question..." },
  send: { zh: "发送", en: "Send" },
  grade: { zh: "年级", en: "Grade" },
  subject: { zh: "学科", en: "Subject" },
  count: { zh: "题数", en: "Count" },
  newQuiz: { zh: "出题", en: "New Quiz" },
  submit: { zh: "提交判分", en: "Submit" },
  score: { zh: "得分", en: "Score" },
  correctAnswer: { zh: "正确答案", en: "Answer" },
  theme: { zh: "主题", en: "Theme" },
  language: { zh: "语言", en: "Language" },
  student: { zh: "学生 ID", en: "Student ID" },
  online: { zh: "在线", en: "Online" },
  offline: { zh: "离线", en: "Offline" },
  backendDown: { zh: "后端未连接", en: "Backend offline" },
  consentTitle: { zh: "家长知情同意", en: "Parent Consent" },
  consentParentName: { zh: "家长/监护人姓名", en: "Parent / Guardian name" },
  consentAgree: { zh: "我已阅读并同意", en: "I agree" },
  consentSubmitting: { zh: "提交中…", en: "Submitting…" },
  consentLoading: { zh: "加载隐私说明…", en: "Loading policy…" },
  consentHint: { zh: "仅收集学习所需数据，可随时申请导出或删除。", en: "We only collect learning data. Export or delete anytime." },
  consentLoadError: { zh: "无法加载隐私说明", en: "Failed to load policy" },
  consentSubmitError: { zh: "提交失败，请重试", en: "Submit failed, please retry" },
  promptSuggestions: { zh: "试试这样问", en: "Try asking" },
};

export function t(key: keyof typeof STRINGS, lang: Lang): string {
  return STRINGS[key]?.[lang] ?? key;
}

/** 12 套主题的中英文显示名 */
export const THEME_NAMES: Record<ThemeName, { zh: string; en: string; swatch: string }> = {
  ocean: { zh: "海洋", en: "Ocean", swatch: "linear-gradient(135deg,#a8edea,#fed6e3)" },
  candy: { zh: "糖果", en: "Candy", swatch: "linear-gradient(135deg,#fbc2eb,#a6c1ee)" },
  forest: { zh: "森林", en: "Forest", swatch: "linear-gradient(135deg,#d4fc79,#96e6a1)" },
  sunset: { zh: "晚霞", en: "Sunset", swatch: "linear-gradient(135deg,#ffecd2,#fcb69f)" },
  lavender: { zh: "薰衣草", en: "Lavender", swatch: "linear-gradient(135deg,#e0c3fc,#8ec5fc)" },
  mint: { zh: "薄荷", en: "Mint", swatch: "linear-gradient(135deg,#c1fba4,#84fab0)" },
  peach: { zh: "蜜桃", en: "Peach", swatch: "linear-gradient(135deg,#ffd6a5,#ffadad)" },
  sky: { zh: "天空", en: "Sky", swatch: "linear-gradient(135deg,#c2e9fb,#a1c4fd)" },
  rose: { zh: "玫瑰", en: "Rose", swatch: "linear-gradient(135deg,#ffe0ec,#ffc3a0)" },
  lemon: { zh: "柠檬", en: "Lemon", swatch: "linear-gradient(135deg,#fff3a0,#c2e9fb)" },
  galaxy: { zh: "银河", en: "Galaxy", swatch: "linear-gradient(135deg,#4b0082,#1e1b4b)" },
  aurora: { zh: "极光", en: "Aurora", swatch: "linear-gradient(135deg,#00c9ff,#92fe9d)" },
};

/** 主题列表（顺序即展示顺序） */
export const THEME_LIST = Object.keys(THEME_NAMES) as ThemeName[];

export const GRADES = ["一年级", "二年级", "三年级", "四年级", "五年级", "六年级"];
export const SUBJECTS = ["数学", "语文", "科学", "英语"];
