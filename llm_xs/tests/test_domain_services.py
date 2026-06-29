"""领域模型、出题/判分、离线问答、文本清洗。"""

from __future__ import annotations

import pytest

from app.domain import Grade, Question, Quiz, Subject
from app.offline import offline_answer
from app.services import generate_quiz, grade_quiz
from app.services.text_utils import clean_answer, clean_text


def test_grade_and_subject_parse():
    assert Grade.parse("三年级") is Grade.GRADE_3
    assert Grade.parse(3) is Grade.GRADE_3
    assert Subject.parse("math") is Subject.MATH
    assert Subject.parse("科普") is Subject.SCIENCE


def test_grade_parse_invalid():
    with pytest.raises(ValueError, match="年级"):
        Grade.parse("大学一年级")


def test_subject_parse_invalid():
    with pytest.raises(ValueError, match="学科"):
        Subject.parse("物理")


def test_quiz_deterministic_with_seed():
    q1 = generate_quiz("三年级", "数学", count=5, seed=42)
    q2 = generate_quiz("三年级", "数学", count=5, seed=42)
    assert [x.prompt for x in q1.questions] == [x.prompt for x in q2.questions]


def test_quiz_public_dict_hides_answers():
    quiz = generate_quiz("二年级", "语文", count=3, seed=1)
    public = quiz.public_dict()
    assert "answer" not in str(public)
    assert len(public["questions"]) == 3
    assert public["questions"][0]["prompt"]


def test_quiz_non_math_subjects():
    for subj in ("语文", "英语", "科学"):
        q = generate_quiz("四年级", subj, count=4, seed=0)
        assert len(q.questions) == 4
        assert all(x.answer for x in q.questions)


def test_grade_quiz_dict_and_list():
    quiz = generate_quiz("三年级", "数学", count=3, seed=9)
    all_correct = {str(q.index): q.answer for q in quiz.questions}
    r1 = grade_quiz(quiz, all_correct)
    assert r1.score == 100
    assert r1.correct == 3

    list_answers = [q.answer for q in quiz.questions]
    r2 = grade_quiz(quiz, list_answers)
    assert r2.score == 100


def test_grade_numeric_equivalence():
    quiz = Quiz(
        grade=Grade.GRADE_3,
        subject=Subject.MATH,
        questions=[Question(index=1, prompt="1+1=?", answer="2", explanation="")],
    )
    result = grade_quiz(quiz, {"1": "2.0"})
    assert result.items[0].is_correct is True


def test_grade_empty_answer():
    quiz = generate_quiz("一年级", "数学", count=2, seed=3)
    result = grade_quiz(quiz, {"1": "", "2": "wrong"})
    empty_item = next(i for i in result.items if i.index == 1)
    assert empty_item.is_correct is False
    assert "留空" in empty_item.feedback or "还没写" in empty_item.feedback


def test_clean_text_and_answer():
    assert clean_text("  你好\x00世界  ") == "你好世界"
    assert clean_answer("  １２３  ") == "123"
    assert clean_text(None) == ""


def test_offline_arithmetic():
    ans = offline_answer("125 + 38 = ?")
    assert "163" in ans


def test_offline_date():
    ans = offline_answer("今天星期几")
    assert "星期" in ans


def test_offline_empty():
    assert "想问" in offline_answer("   ")


def test_offline_fallback(keyword_backend):
    from app.knowledge import build_index

    build_index()
    ans = offline_answer("太阳系有几大行星")
    assert "知识库" in ans or "行星" in ans or "离线" in ans
