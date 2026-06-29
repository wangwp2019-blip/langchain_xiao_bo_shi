"""判分引擎：对照标准答案判分，生成每题反馈与整体鼓励性总结。

判分采用"清洗后比较"：忽略全角/空白差异；数字答案做数值等价比较
（例如 "18" 与 "18.0" 视为相同）。
"""

from __future__ import annotations

from ..domain import GradedItem, GradeResult, Question, Quiz
from .encouragement import correct_feedback, summary_feedback, wrong_feedback
from .text_utils import clean_answer


def _answers_match(user: str, correct: str) -> bool:
    u, c = clean_answer(user), clean_answer(correct)
    if not u:
        return False
    if u == c:
        return True
    # 数值等价比较
    try:
        return abs(float(u) - float(c)) < 1e-9
    except ValueError:
        return u.lower() == c.lower()


def grade_quiz(quiz: Quiz, answers: dict[int, str] | list[str]) -> GradeResult:
    """判分。

    ``answers`` 支持两种形式：
    - dict：``{题号: 答案}``
    - list：按题序排列的答案列表（缺失用空串）
    """
    answer_map: dict[int, str] = {}
    if isinstance(answers, dict):
        for k, v in answers.items():
            try:
                answer_map[int(k)] = "" if v is None else str(v)
            except (TypeError, ValueError):
                continue
    else:
        for i, v in enumerate(answers, start=1):
            answer_map[i] = "" if v is None else str(v)

    items: list[GradedItem] = []
    correct = 0
    for q in quiz.questions:
        raw = answer_map.get(q.index, "")
        user = clean_answer(raw)
        is_correct = _answers_match(user, q.answer)
        if is_correct:
            correct += 1
            feedback = correct_feedback()
            explanation = ""
        else:
            feedback = wrong_feedback(empty=(user == ""))
            explanation = q.explanation
        items.append(
            GradedItem(
                index=q.index,
                prompt=q.prompt,
                user_answer=user,
                correct_answer=q.answer,
                is_correct=is_correct,
                feedback=feedback,
                explanation=explanation,
            )
        )

    total = len(quiz.questions)
    score = round(correct / total * 100) if total else 0
    return GradeResult(
        total=total,
        correct=correct,
        score=score,
        summary=summary_feedback(correct, total),
        items=items,
    )


def grade_raw(questions: list[Question], answers: dict[int, str] | list[str], grade, subject) -> GradeResult:
    """便捷重载：用题目列表直接判分（内部包成 Quiz）。"""
    quiz = Quiz(grade=grade, subject=subject, questions=questions)
    return grade_quiz(quiz, answers)
