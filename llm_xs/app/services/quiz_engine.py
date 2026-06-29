"""出题引擎：按「年级 + 学科」生成 10 道题（纯离线，无需大模型）。

- 数学：按年级难度随机生成四则运算（一二年级以加减为主，三年级起含乘除，
  高年级数值更大、含两步运算）。
- 语文 / 英语 / 科学：内置小题库，按年级挑选；题库不足时循环取用。

设计为确定性可控：可传入 ``seed`` 复现同一套题（便于测试 / 演示）。
"""

from __future__ import annotations

import random

from ..domain import Grade, Question, Quiz, Subject

_DEFAULT_COUNT = 10


def generate_quiz(
    grade: Grade | str | int,
    subject: Subject | str,
    count: int = _DEFAULT_COUNT,
    seed: int | None = None,
) -> Quiz:
    """生成一套练习题。"""
    g = Grade.parse(grade)
    s = Subject.parse(subject)
    rng = random.Random(seed)
    count = max(1, min(50, count))

    if s is Subject.MATH:
        questions = _gen_math(g, count, rng)
    else:
        questions = _gen_from_bank(g, s, count, rng)
    return Quiz(grade=g, subject=s, questions=questions)


def _gen_math(grade: Grade, count: int, rng: random.Random) -> list[Question]:
    level = grade.level
    questions: list[Question] = []
    for i in range(1, count + 1):
        prompt, answer, expl = _one_math(level, rng)
        questions.append(
            Question(index=i, prompt=prompt, answer=str(answer), explanation=expl)
        )
    return questions


def _one_math(level: int, rng: random.Random) -> tuple[str, int, str]:
    """根据年级难度生成一道四则运算题。"""
    if level <= 1:
        a, b = rng.randint(1, 10), rng.randint(1, 10)
        if rng.random() < 0.5:
            return f"{a} + {b} = ?", a + b, f"{a} + {b} 就是把两个数合起来，等于 {a + b}。"
        a, b = max(a, b), min(a, b)
        return f"{a} - {b} = ?", a - b, f"{a} 减去 {b}，等于 {a - b}。"
    if level == 2:
        op = rng.choice(["+", "-", "×"])
        if op == "×":
            a, b = rng.randint(2, 9), rng.randint(2, 9)
            return f"{a} × {b} = ?", a * b, f"{a} × {b} 就是 {b} 个 {a} 相加，等于 {a * b}。"
        a, b = rng.randint(10, 50), rng.randint(1, 40)
        if op == "-":
            a, b = max(a, b), min(a, b)
            return f"{a} - {b} = ?", a - b, f"{a} 减 {b} 等于 {a - b}。"
        return f"{a} + {b} = ?", a + b, f"{a} 加 {b} 等于 {a + b}。"
    if level == 3:
        op = rng.choice(["×", "÷", "+", "-"])
        if op == "×":
            a, b = rng.randint(2, 9), rng.randint(2, 9)
            return f"{a} × {b} = ?", a * b, f"{a} × {b} 就是 {b} 个 {a} 相加，等于 {a * b}。"
        if op == "÷":
            b, q = rng.randint(2, 9), rng.randint(2, 9)
            a = b * q
            return f"{a} ÷ {b} = ?", q, f"{a} 里有 {q} 个 {b}，所以等于 {q}。"
        a, b = rng.randint(20, 100), rng.randint(10, 90)
        if op == "-":
            a, b = max(a, b), min(a, b)
            return f"{a} - {b} = ?", a - b, f"{a} 减 {b} 等于 {a - b}。"
        return f"{a} + {b} = ?", a + b, f"{a} 加 {b} 等于 {a + b}。"
    # 4~6 年级：更大数值 + 两步运算
    style = rng.choice(["two_step", "mul", "div"])
    if style == "mul":
        a, b = rng.randint(11, 30), rng.randint(2, 12)
        return f"{a} × {b} = ?", a * b, f"{a} × {b} = {a * b}。"
    if style == "div":
        b, q = rng.randint(3, 12), rng.randint(3, 12)
        a = b * q
        return f"{a} ÷ {b} = ?", q, f"{a} ÷ {b} = {q}。"
    a, b, c = rng.randint(2, 9), rng.randint(2, 9), rng.randint(1, 20)
    return (
        f"{a} × {b} + {c} = ?",
        a * b + c,
        f"先算 {a} × {b} = {a * b}，再加 {c}，等于 {a * b + c}。",
    )


# ---- 非数学学科的内置小题库（题面, 答案, 讲解）----
_BANK: dict[Subject, list[tuple[str, str, str]]] = {
    Subject.CHINESE: [
        ("'太阳'的'阳'是几画？（填数字）", "6", "'阳'共 6 画：横折折折钩等，按笔顺数。"),
        ("'春'字下面是什么字？", "日", "'春'下半部分是'日'。"),
        ("反义词：大 → ?", "小", "'大'的反义词是'小'。"),
        ("反义词：上 → ?", "下", "'上'的反义词是'下'。"),
        ("'马'的拼音声母是？", "m", "'马'拼音 mǎ，声母是 m。"),
        ("把'我爱学习'倒过来读，第一个字是？", "习", "倒读为'习学爱我'。"),
        ("'江河湖海'都和什么有关？", "水", "这些字都带三点水，与水有关。"),
        ("近义词：高兴 → ?（写一个）", "快乐", "高兴≈快乐/开心。"),
    ],
    Subject.ENGLISH: [
        ("apple 的中文意思是？", "苹果", "apple = 苹果。"),
        ("'猫'的英文是？", "cat", "猫 = cat。"),
        ("one, two, ? （填英文）", "three", "1,2,3 = one,two,three。"),
        ("red 的中文意思是？", "红色", "red = 红色。"),
        ("'狗'的英文是？", "dog", "狗 = dog。"),
        ("字母表第一个字母是？", "a", "26 个字母第一个是 A/a。"),
        ("book 的中文意思是？", "书", "book = 书。"),
        ("'你好'的英文是？", "hello", "你好 = hello。"),
    ],
    Subject.SCIENCE: [
        ("太阳系里离太阳最近的行星是？", "水星", "顺序：水金地火……最近的是水星。"),
        ("水在 0 摄氏度会变成什么？", "冰", "0℃ 水会结成冰。"),
        ("植物进行光合作用需要什么气体？", "二氧化碳", "光合作用吸收二氧化碳、放出氧气。"),
        ("彩虹有几种主要颜色？（填数字）", "7", "赤橙黄绿青蓝紫，共 7 种。"),
        ("一年有几个季节？（填数字）", "4", "春夏秋冬，共 4 个季节。"),
        ("人用什么器官呼吸？", "肺", "人靠肺进行呼吸。"),
        ("地球的天然卫星是？", "月球", "月球是地球唯一的天然卫星。"),
        ("蜜蜂采集什么来酿蜜？", "花蜜", "蜜蜂采花蜜酿成蜂蜜。"),
    ],
}


def _gen_from_bank(
    grade: Grade, subject: Subject, count: int, rng: random.Random
) -> list[Question]:
    bank = list(_BANK.get(subject, []))
    rng.shuffle(bank)
    questions: list[Question] = []
    for i in range(1, count + 1):
        prompt, answer, expl = bank[(i - 1) % len(bank)]
        questions.append(
            Question(index=i, prompt=prompt, answer=answer, explanation=expl)
        )
    return questions
