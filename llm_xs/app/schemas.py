"""结构化输出的数据模型（配合 ToolStrategy 使用）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class StudyCard(BaseModel):
    """给小学生的"学习卡片"，把答案整理成结构化、好理解的形式。"""

    topic: str = Field(description="问题所属的学科或主题，例如：语文、数学、科学、安全、健康")
    answer: str = Field(description="用小学生能听懂的简单语言给出的答案，2 到 4 句话")
    knowledge_points: list[str] = Field(description="涉及的关键知识点，每条简短一句")
    example: str = Field(description="一个贴近小学生生活的小例子，帮助理解")
    encouragement: str = Field(description="一句温暖、鼓励小朋友的话")
