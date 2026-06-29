"""离线降级问答：未配置大模型 Key 时也能给出友好、有用的回答。

能力（纯本地）：
- **算式直算**：识别 "125 + 38 = ?" 这类纯算式，直接给出答案。
- **日期**：识别"今天几号 / 星期几"。
- **知识库兜底**：尝试本地 RAG 检索（keyword 后端可零 Embedding 运行）。
- **温和兜底**：其它问题给出鼓励性提示，引导在线模式或问老师家长。

在线模式异常时也可调用本模块兜底，绝不把报错丢给孩子。
"""

from __future__ import annotations

import ast
import logging
import operator
import re
from datetime import datetime

logger = logging.getLogger(__name__)

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# 仅含数字、运算符、括号、等号、问号、空白：判定为"算式"
_ARITH_RE = re.compile(r"^[\d\s\.\+\-\*/%×÷()=?？]+$")


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("不支持的表达式")


def _try_arithmetic(text: str) -> str | None:
    expr = text.replace("×", "*").replace("÷", "/")
    expr = expr.replace("=", "").replace("?", "").replace("？", "").strip()
    if not expr or not _ARITH_RE.match(text):
        return None
    if not any(op in expr for op in "+-*/%"):
        return None
    try:
        result = _safe_eval(ast.parse(expr, mode="eval").body)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return f"小朋友，这道题的答案是 {result} 哦～你也可以自己再算一遍验证一下！🌟"
    except Exception:  # noqa: BLE001
        return None


def _try_date(text: str) -> str | None:
    if any(k in text for k in ("几号", "几月", "今天", "星期几", "礼拜几")):
        now = datetime.now()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        return now.strftime("今天是 %Y年%m月%d日，") + weekdays[now.weekday()]
    return None


def _try_knowledge(text: str) -> str | None:
    try:
        from .knowledge import format_context, retrieve

        hits = retrieve(text)
        if hits:
            top = hits[0].get("text", "").strip()
            if top:
                snippet = top[:160]
                return f"小朋友，我在小知识库里找到了这个：\n{snippet}\n要不要再问得具体一点呀？😊"
    except Exception as exc:  # noqa: BLE001
        logger.debug("离线知识库检索失败（忽略）：%s", exc)
    return None


_FALLBACK = (
    "小朋友，这个问题有点难，小博士现在是离线小模式哦～🌈 "
    "你可以让大人帮忙打开在线模式，我就能讲得更清楚啦！"
    "也可以先问问老师或爸爸妈妈～"
)


def offline_answer(question: str) -> str:
    """离线问答主入口：依次尝试算式 / 日期 / 知识库 / 兜底。"""
    text = (question or "").strip()
    if not text:
        return "小朋友，你想问什么呀？把问题告诉我吧～😊"
    for handler in (_try_arithmetic, _try_date, _try_knowledge):
        reply = handler(text)
        if reply:
            return reply
    return _FALLBACK
