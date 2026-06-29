"""安全层：儿童内容安全护栏（纯本地、零依赖、可热配置）。

三件事：
1. **输入判定**：三级——正常 / 引导（不适宜话题，温和劝导）/ 拦截（明确有害）。
2. **输出净化**：把负面、打击性措辞替换为正向表达，兜底守住"零负面"。
3. **词库外部化**：默认内置词表，可通过 ``KIDS_SAFETY_WORDS_PATH`` 指向自定义
   JSON 与内置合并，便于按学校/地区/年龄段定制。

JSON 结构（均可选）::

    {
      "block_words": ["..."],
      "redirect_patterns": ["..."],
      "negative_replacements": {"笨": "还在学习中"}
    }
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

from .audit import safety_triggered
from .config import settings

logger = logging.getLogger(__name__)

# 明确有害 / 完全不适合儿童：直接拦截。
_BLOCK_WORDS = [
    "打架", "脏话", "色情", "暴力", "毒品", "自杀", "自残",
    "赌博", "枪支", "炸弹", "恐怖袭击",
]

# 成人 / 隐私 / 超纲等不适宜话题：温和引导去问老师或家长。
_REDIRECT_WORDS = [
    "谈恋爱", "结婚", "身份证", "银行卡", "家庭住址", "电话号码",
    "信用卡", "密码",
]

# 输出净化：负面/打击措辞 -> 正向表达。
_NEGATIVE_REPLACEMENTS = {
    "笨": "还在学习中",
    "蠢": "还在学习中",
    "傻": "可爱",
    "废物": "小可爱",
    "没用": "很努力",
    "失败者": "勇敢的小朋友",
    "白痴": "小机灵",
}

_REDIRECT_REPLY = (
    "小朋友，这个话题不太适合我们现在聊哦～🌈 "
    "可以问问老师或者爸爸妈妈。我们换个有趣的问题好不好？"
    "比如数学小窍门，或者一个好玩的科普知识，我超想和你一起探索的！"
)

_BLOCK_REPLY = (
    "小朋友，这个话题小博士不能聊哦～🌟 "
    "如果你遇到困扰，一定要告诉信任的老师或家长。"
    "我们来聊点开心又有用的吧，比如读一首小诗，或者算一道有趣的题～"
)


class SafetyAction(str, Enum):
    ALLOW = "allow"
    REDIRECT = "redirect"
    BLOCK = "block"


@dataclass
class SafetyVerdict:
    action: SafetyAction
    reply: str | None = None  # 命中 redirect/block 时的适龄回复
    matched: str | None = None

    @property
    def allowed(self) -> bool:
        return self.action is SafetyAction.ALLOW


@dataclass
class _Rules:
    block_words: list[str]
    redirect_words: list[str]
    negative_replacements: dict[str, str]


@lru_cache(maxsize=1)
def _load_rules() -> _Rules:
    block = list(_BLOCK_WORDS)
    redirect = list(_REDIRECT_WORDS)
    replacements = dict(_NEGATIVE_REPLACEMENTS)

    path = settings.safety_words_path
    if path:
        try:
            raw = json.loads(open(path, encoding="utf-8").read())
            block += list(raw.get("block_words", []))
            redirect += list(raw.get("redirect_patterns", []))
            replacements.update(raw.get("negative_replacements", {}) or {})
            logger.info("已加载自定义安全词库：%s", path)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("加载安全词库失败（忽略，使用内置）：%s", exc)

    return _Rules(
        block_words=sorted(set(block), key=len, reverse=True),
        redirect_words=sorted(set(redirect), key=len, reverse=True),
        negative_replacements=replacements,
    )


def check_input(text: str, *, request_id: str = "-", principal: str = "-") -> SafetyVerdict:
    """输入侧三级判定 + 可选 OpenAI Moderation。"""
    rules = _load_rules()
    lowered = (text or "")
    for word in rules.block_words:
        if word and word in lowered:
            verdict = SafetyVerdict(SafetyAction.BLOCK, _BLOCK_REPLY, word)
            safety_triggered("block", matched=word, request_id=request_id, principal=principal)
            return verdict
    for word in rules.redirect_words:
        if word and word in lowered:
            verdict = SafetyVerdict(SafetyAction.REDIRECT, _REDIRECT_REPLY, word)
            safety_triggered("redirect", matched=word, request_id=request_id, principal=principal)
            return verdict

    mod = _check_openai_moderation(text)
    if mod is not None:
        if not mod.allowed:
            safety_triggered(
                mod.action.value,
                matched=mod.matched,
                request_id=request_id,
                principal=principal,
            )
        return mod
    return SafetyVerdict(SafetyAction.ALLOW)


def reload_rules() -> None:
    """热加载外部词库（文件更新后调用）。"""
    _load_rules.cache_clear()


def _check_openai_moderation(text: str) -> SafetyVerdict | None:
    """可选 OpenAI Moderation API（配置 ``KIDS_MODERATION_ENABLED=true`` 启用）。"""
    if not settings.moderation_configured:
        return None
    try:
        import httpx

        base = (settings.moderation_base_url or "https://api.openai.com/v1").rstrip("/")
        url = f"{base}/moderations"
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {settings.moderation_api_key}"},
            json={"input": text},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results") or []
        if not results:
            return None
        r0 = results[0]
        if r0.get("flagged"):
            cats = r0.get("categories") or {}
            if cats.get("sexual") or cats.get("violence") or cats.get("self-harm"):
                return SafetyVerdict(SafetyAction.BLOCK, _BLOCK_REPLY, "moderation")
            return SafetyVerdict(SafetyAction.REDIRECT, _REDIRECT_REPLY, "moderation")
    except Exception as exc:
        if settings.moderation_fail_open:
            logger.warning("OpenAI Moderation 调用失败（fail-open 放行）: %s", exc)
            return None
        logger.warning("OpenAI Moderation 调用失败（fail-closed 拦截）: %s", exc)
        return SafetyVerdict(SafetyAction.BLOCK, _BLOCK_REPLY, "moderation_unavailable")
    return None


def sanitize_output(text: str) -> str:
    """输出侧净化：替换负面措辞；可选 Moderation 输出审核。"""
    if not text:
        return text
    rules = _load_rules()
    cleaned = text
    for bad, good in rules.negative_replacements.items():
        if bad in cleaned:
            cleaned = cleaned.replace(bad, good)
    mod = _check_openai_moderation(cleaned)
    if mod is not None and not mod.allowed:
        return mod.reply or _BLOCK_REPLY
    return cleaned
