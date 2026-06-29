"""文本清洗：把脏输入（空白 / 乱码 / 超长 / 全角符号）规整成可用文本。

健壮性原则：无论输入多脏，都不抛异常、不崩溃，返回安全可用的字符串。
"""

from __future__ import annotations

import re

_MAX_LEN = 2000
_WHITESPACE_RE = re.compile(r"\s+")

# 常见全角数字/符号 -> 半角，便于答案比对（小朋友常打出全角）。
_FULL_TO_HALF = {
    "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
    "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
    "．": ".", "－": "-", "＋": "+", "／": "/",
    "（": "(", "）": ")", "　": " ",
}


def _to_half_width(text: str) -> str:
    return "".join(_FULL_TO_HALF.get(ch, ch) for ch in text)


def clean_text(value: object, *, max_len: int = _MAX_LEN) -> str:
    """通用文本清洗：转字符串、去首尾空白、压缩连续空白、截断超长。"""
    if value is None:
        return ""
    text = str(value)
    text = _to_half_width(text)
    text = text.replace("\x00", "")
    text = text.strip()
    if len(text) > max_len:
        text = text[:max_len]
    return text


def clean_answer(value: object) -> str:
    """答案清洗：在 clean_text 基础上去掉内部多余空白，统一比较口径。"""
    text = clean_text(value, max_len=128)
    text = _WHITESPACE_RE.sub("", text)
    return text
