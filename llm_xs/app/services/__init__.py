"""服务层：出题 / 判分 / 鼓励反馈 / 文本清洗（纯 Python，离线可跑）。"""

from .encouragement import correct_feedback, summary_feedback, wrong_feedback
from .grading_engine import grade_quiz
from .quiz_engine import generate_quiz
from .text_utils import clean_answer, clean_text

__all__ = [
    "generate_quiz",
    "grade_quiz",
    "correct_feedback",
    "wrong_feedback",
    "summary_feedback",
    "clean_text",
    "clean_answer",
]
