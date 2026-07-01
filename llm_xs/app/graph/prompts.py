"""图节点共用的 Prompt 模板与构建器。

支持：
- 默认/文件/环境变量扩展 System Prompt（``KIDS_SYSTEM_PROMPT_FILE`` / ``KIDS_SYSTEM_PROMPT_EXTRA``）
- 按学生 profile + 长期记忆注入个性化上下文
- 学习卡片 User Prompt 模板
- 前端快捷提问建议（``GET /api/prompts/suggestions``）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..config import settings

DEFAULT_KIDS_SYSTEM_PROMPT = """你是"小博士"，一个专门陪伴 6 到 12 岁小学生学习的 AI 伙伴。

【说话方式】
1. 用简单、亲切、有耐心的语气，像大哥哥大姐姐一样，多用小朋友熟悉的例子和比喻。
2. 句子要短，避免难懂的术语；必要时先解释词语的意思。
3. 多鼓励小朋友，肯定他们的好奇心和努力。

【怎么回答】
1. 遇到语文、数学、科学、安全、健康、历史地理等课本相关的问题，先用 search_knowledge_base 查一查知识库，再结合资料回答。
2. 知识库里没有，或者需要最新的、课外的信息时，可以用联网搜索工具帮忙查找。
3. 遇到算式或需要计算时，用 calculator 工具核对结果，不要心算出错。
4. 小朋友问"今天几号""星期几"时，用 get_today_info 工具。
5. 小朋友介绍自己（名字、年级）时，用 save_student_profile 记下来；透露兴趣爱好或薄弱知识点时，用 save_memory 记住；需要时用 get_student_profile / recall_memories 回忆，让陪伴更贴心。

【学习域工具】
6. 问学情/薄弱点时，用 query_learning_gaps 或 get_student_learning_context，必须引用 gap_id/attempt_id，不可臆造。
7. 推荐练习：suggest_learning_questions → question_get 看题面 → submit_learning_attempt 提交答案。
8. 真实作业题：submit_freeform_attempt 纳入学情。
9. 讲解知识点：explain_knowledge_point；拍照文本：classify_homework_photo。
10. 制定计划：create_study_plan。讲新课时优先讲解，不要硬推题。

【安全与原则】
1. 涉及安全和健康的问题（如交通、防溺水、用电用火）必须严谨准确，绝不能编造。
2. 不讨论暴力、恐怖等不适合儿童的内容，温和地引导小朋友去问老师或家长。
3. 不确定的内容要诚实说明，并建议小朋友和老师、家长一起确认。

请始终用简体中文回答。"""

SIMPLE_CHAT_SYSTEM_PROMPT = """你是小博士，一个友好、准确的 AI 助手。

【怎么回答】
1. 用户的问题若可能与资料库相关，**务必先**调用 search_knowledge_base 检索，再结合检索到的内容回答；不要凭空编造资料里的细节。
2. 知识库没有、或需要最新公开信息时，可使用联网搜索工具（若已启用）。
3. 需要算式计算时用 calculator；问今天日期/星期几时用 get_today_info。

【原则】
- 回答简洁清楚，不确定时诚实说明。
- 请用简体中文回答。"""

# 向后兼容：测试与文档仍引用此名
KIDS_SYSTEM_PROMPT = DEFAULT_KIDS_SYSTEM_PROMPT

STUDY_CARD_SYSTEM_PROMPT = (
    "你要根据提供的资料，为小学生整理一张学习卡片。"
    "用简单、鼓励的语言，确保内容准确、适合小学生。"
    "若资料不足，可基于常识简要回答，但不得编造危险或不当内容。"
    "请严格按以下 JSON 格式输出（不要包含其他文字）：\n"
    '{"topic": "学科或主题", "answer": "用小学生能听懂的简单语言给出的答案，2到4句话", '
    '"knowledge_points": ["知识点1", "知识点2"], '
    '"example": "一个贴近小学生生活的小例子，帮助理解", '
    '"encouragement": "一句温暖、鼓励小朋友的话"}'
)


@dataclass
class PromptContext:
    """注入 System Prompt 的学生上下文。"""

    user_id: str | None = None
    name: str | None = None
    grade: str | None = None
    facts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SuggestedPrompt:
    """快捷提问建议。"""

    text_zh: str
    text_en: str
    category_zh: str
    category_en: str
    grades: tuple[str, ...] | None = None  # None 表示全年级


_SUGGESTED: tuple[SuggestedPrompt, ...] = (
    SuggestedPrompt("太阳系有几大行星？", "How many planets are in the solar system?", "科学", "Science"),
    SuggestedPrompt("125 + 38 等于多少？", "What is 125 + 38?", "数学", "Math"),
    SuggestedPrompt("为什么要系安全带？", "Why should we wear seat belts?", "安全", "Safety"),
    SuggestedPrompt("今天几号？星期几？", "What is today's date?", "生活", "Daily"),
    SuggestedPrompt("「春眠不觉晓」是谁写的？", "Who wrote the poem about spring sleep?", "语文", "Chinese"),
    SuggestedPrompt("3 × 7 等于多少？", "What is 3 times 7?", "数学", "Math", ("一年级", "二年级", "三年级")),
    SuggestedPrompt("水的三种状态是什么？", "What are the three states of water?", "科学", "Science", ("三年级", "四年级", "五年级", "六年级")),
    SuggestedPrompt("遇到陌生人搭讪该怎么办？", "What should I do if a stranger talks to me?", "安全", "Safety"),
    SuggestedPrompt("怎样保护眼睛少看屏幕？", "How can I protect my eyes from screens?", "健康", "Health"),
    SuggestedPrompt("分数 1/2 和 1/4 哪个大？", "Which is bigger, 1/2 or 1/4?", "数学", "Math", ("四年级", "五年级", "六年级")),
)


@lru_cache(maxsize=1)
def _load_base_system_prompt() -> str:
    """读取基础 System Prompt（文件优先，否则默认模板）。"""
    path = settings.system_prompt_file
    if path:
        p = Path(path)
        if p.is_file():
            text = p.read_text(encoding="utf-8").strip()
            if text:
                return text
    if settings.simple_chat_mode:
        return SIMPLE_CHAT_SYSTEM_PROMPT
    return DEFAULT_KIDS_SYSTEM_PROMPT


def clear_prompt_cache() -> None:
    """测试或热更新时清除缓存。"""
    _load_base_system_prompt.cache_clear()


def load_prompt_context(user_id: str | None) -> PromptContext:
    """从长期记忆加载学生 profile 与近期事实（失败时返回空上下文）。"""
    if not user_id:
        return PromptContext()
    try:
        from ..memory_admin import list_memories

        data = list_memories(user_id)
        profile = data.get("profile") or {}
        facts: list[str] = []
        for item in (data.get("facts") or [])[:5]:
            val = item.get("value") if isinstance(item, dict) else None
            if val and str(val).strip():
                facts.append(str(val).strip())
        name = (profile.get("name") or "").strip() or None
        grade = (profile.get("grade") or "").strip() or None
        return PromptContext(user_id=user_id, name=name, grade=grade, facts=facts)
    except Exception:
        return PromptContext(user_id=user_id)


def _format_personalization(ctx: PromptContext | None) -> str:
    if not ctx or not (ctx.name or ctx.grade or ctx.facts):
        return ""
    lines = ["\n\n【当前小朋友】"]
    if ctx.name:
        lines.append(f"- 称呼：{ctx.name}")
    if ctx.grade:
        lines.append(f"- 年级：{ctx.grade}（请按该年级课本难度举例和讲解）")
    if ctx.facts:
        lines.append("- 记得的事：" + "；".join(ctx.facts[:5]))
    lines.append("请结合以上信息调整语气、举例难度与鼓励方式。")
    return "\n".join(lines)


def build_kids_system_prompt(ctx: PromptContext | None = None) -> str:
    """构建主对话 System Prompt（含可选个性化与 KIDS_SYSTEM_PROMPT_EXTRA）。"""
    if settings.simple_chat_mode:
        parts = [_load_base_system_prompt()]
    else:
        parts = [_load_base_system_prompt(), _format_personalization(ctx)]
    extra = (settings.system_prompt_extra or "").strip()
    if extra:
        parts.append(f"\n\n【补充说明】\n{extra}")
    return "".join(parts)


def build_study_card_user_prompt(question: str, context: str, *, grade: str | None = None) -> str:
    """学习卡片 User Prompt。"""
    grade_hint = f"（小朋友年级：{grade}）" if grade else ""
    return (
        f"小朋友的问题{grade_hint}：{question.strip()}\n\n"
        f"可参考的资料：\n{context.strip() or '（知识库中没有找到相关内容）'}"
    )


def get_suggested_prompts(
    *,
    grade: str | None = None,
    lang: str = "zh",
    limit: int = 8,
) -> list[dict[str, Any]]:
    """返回快捷提问列表（供 API / 前端）。"""
    use_en = lang.lower().startswith("en")
    out: list[dict[str, Any]] = []
    for item in _SUGGESTED:
        if grade and item.grades and grade not in item.grades:
            continue
        out.append(
            {
                "text": item.text_en if use_en else item.text_zh,
                "category": item.category_en if use_en else item.category_zh,
            }
        )
        if len(out) >= limit:
            break
    if len(out) < limit:
        for item in _SUGGESTED:
            if any(p["text"] == (item.text_en if use_en else item.text_zh) for p in out):
                continue
            out.append(
                {
                    "text": item.text_en if use_en else item.text_zh,
                    "category": item.category_en if use_en else item.category_zh,
                }
            )
            if len(out) >= limit:
                break
    return out
