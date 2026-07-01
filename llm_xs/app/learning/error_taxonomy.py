"""错因 → 知识点 / 能力维度 映射。"""

from __future__ import annotations

ERROR_TO_KP: dict[str, str] = {
    "CARRY_ERROR": "kp-g2-add-carry",
    "BORROW_ERROR": "kp-g2-sub-borrow",
    "ALIGN_ERROR": "kp-g2-align-digits",
    "CHAIN_ERROR": "kp-g2-add-sub-chain",
    "MIXED_ERROR": "kp-g2-add-sub-mixed",
    "WORD_MORE_LESS": "kp-g2-word-problem-more-less",
    "MULT_MEANING": "kp-g2-mult-meaning",
    "MULT_TABLE": "kp-g2-mult-table-2",
    "GENERIC_MATH": "kp-g2-add-no-carry",
}

ERROR_TO_DIMENSION: dict[str, str] = {
    "CARRY_ERROR": "基础知识",
    "BORROW_ERROR": "基础知识",
    "ALIGN_ERROR": "审题能力",
    "CHAIN_ERROR": "逻辑推理",
    "MIXED_ERROR": "逻辑推理",
    "WORD_MORE_LESS": "审题能力",
    "GENERIC_MATH": "基础知识",
}

MASTERED_STREAK = 3


def infer_error_code(prompt: str, student_answer: str, correct: str) -> str | None:
    """规则推断错因（离线/兜底）。"""
    if student_answer.strip() == correct.strip():
        return None
    p = prompt + student_answer
    if "退" in p or "借" in p:
        return "BORROW_ERROR"
    if "进" in p or "满十" in p:
        return "CARRY_ERROR"
    if "对齐" in p or "数位" in p:
        return "ALIGN_ERROR"
    if "比" in prompt and ("多" in prompt or "少" in prompt):
        return "WORD_MORE_LESS"
    if "+" in prompt and len(prompt) > 10:
        return "CARRY_ERROR"
    if "-" in prompt:
        return "BORROW_ERROR"
    return "GENERIC_MATH"


def kp_for_error(error_code: str | None) -> str:
    if not error_code:
        return "kp-g2-add-no-carry"
    return ERROR_TO_KP.get(error_code, "kp-g2-add-no-carry")
