"""领域层：纯数据模型与枚举（不依赖任何外部服务，离线可用）。

这一层只描述"业务概念长什么样"：年级、学科、题目、判分结果。
不包含任何 IO / 网络 / 数据库逻辑，便于单测与离线运行。
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Grade(str, Enum):
    """小学年级（1~6 年级）。"""

    GRADE_1 = "一年级"
    GRADE_2 = "二年级"
    GRADE_3 = "三年级"
    GRADE_4 = "四年级"
    GRADE_5 = "五年级"
    GRADE_6 = "六年级"

    @property
    def level(self) -> int:
        """返回数字年级（1~6），便于按难度生成题目。"""
        return {
            Grade.GRADE_1: 1,
            Grade.GRADE_2: 2,
            Grade.GRADE_3: 3,
            Grade.GRADE_4: 4,
            Grade.GRADE_5: 5,
            Grade.GRADE_6: 6,
        }[self]

    @classmethod
    def parse(cls, value: "Grade | str | int") -> "Grade":
        """宽松解析：支持枚举、"三年级"、"3"、3 等多种写法。"""
        if isinstance(value, Grade):
            return value
        if isinstance(value, int):
            return cls._from_level(value)
        text = str(value).strip()
        for member in cls:
            if member.value == text:
                return member
        digits = "".join(ch for ch in text if ch.isdigit())
        if digits:
            return cls._from_level(int(digits))
        raise ValueError(f"无法识别的年级：{value!r}")

    @classmethod
    def _from_level(cls, level: int) -> "Grade":
        level = max(1, min(6, level))
        return {
            1: cls.GRADE_1,
            2: cls.GRADE_2,
            3: cls.GRADE_3,
            4: cls.GRADE_4,
            5: cls.GRADE_5,
            6: cls.GRADE_6,
        }[level]


class Subject(str, Enum):
    """学科。"""

    MATH = "数学"
    CHINESE = "语文"
    SCIENCE = "科学"
    ENGLISH = "英语"

    @classmethod
    def parse(cls, value: "Subject | str") -> "Subject":
        if isinstance(value, Subject):
            return value
        text = str(value).strip()
        aliases = {
            "math": cls.MATH,
            "数学": cls.MATH,
            "chinese": cls.CHINESE,
            "语文": cls.CHINESE,
            "science": cls.SCIENCE,
            "科学": cls.SCIENCE,
            "科普": cls.SCIENCE,
            "english": cls.ENGLISH,
            "英语": cls.ENGLISH,
        }
        key = text.lower()
        if key in aliases:
            return aliases[key]
        for member in cls:
            if member.value == text:
                return member
        raise ValueError(f"无法识别的学科：{value!r}")


class Question(BaseModel):
    """一道题目。"""

    index: int = Field(description="题号，从 1 开始")
    prompt: str = Field(description="题面，例如 '3 × 6 = ?'")
    answer: str = Field(description="标准答案（字符串，便于统一比较）")
    explanation: str = Field(default="", description="讲解，答错时展示")


class Quiz(BaseModel):
    """一套练习题。"""

    grade: Grade
    subject: Subject
    questions: list[Question]

    def public_dict(self) -> dict:
        """对外返回时隐藏答案（避免前端直接拿到答案）。"""
        return {
            "grade": self.grade.value,
            "subject": self.subject.value,
            "questions": [
                {"index": q.index, "prompt": q.prompt} for q in self.questions
            ],
        }


class GradedItem(BaseModel):
    """单题判分结果。"""

    index: int
    prompt: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    feedback: str
    explanation: str = ""


class GradeResult(BaseModel):
    """整套判分结果。"""

    total: int
    correct: int
    score: int = Field(description="百分制得分")
    summary: str = Field(description="整体鼓励性总结")
    items: list[GradedItem]
