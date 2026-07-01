"""按 KP 绑定的题库（P0 选题非生题）。"""

from __future__ import annotations

from .schemas import QuestionPublic

# question_id → 完整题（含答案，仅服务端）
_BANK: dict[str, dict] = {
    "q-g2-carry-01": {
        "prompt": "37 + 28 = ?",
        "answer": "65",
        "knowledge_point_id": "kp-g2-add-carry",
        "unit_id": "math-g2-add-sub-100",
        "grade": 2,
        "subject": "数学",
        "explanation": "个位 7+8=15，写 5 进 1；十位 3+2+1=6。",
    },
    "q-g2-carry-02": {
        "prompt": "46 + 39 = ?",
        "answer": "85",
        "knowledge_point_id": "kp-g2-add-carry",
        "unit_id": "math-g2-add-sub-100",
        "grade": 2,
        "subject": "数学",
        "explanation": "个位满十向十位进 1。",
    },
    "q-g2-borrow-01": {
        "prompt": "52 - 27 = ?",
        "answer": "25",
        "knowledge_point_id": "kp-g2-sub-borrow",
        "unit_id": "math-g2-add-sub-100",
        "grade": 2,
        "subject": "数学",
        "explanation": "个位 2 不够减 7，从十位退 1 当 10。",
    },
    "q-g2-borrow-02": {
        "prompt": "63 - 48 = ?",
        "answer": "15",
        "knowledge_point_id": "kp-g2-sub-borrow",
        "unit_id": "math-g2-add-sub-100",
        "grade": 2,
        "subject": "数学",
        "explanation": "退位减法。",
    },
    "q-g2-align-01": {
        "prompt": "竖式计算时为什么要相同数位对齐？",
        "answer": "个位对个位十位对十位",
        "knowledge_point_id": "kp-g2-align-digits",
        "unit_id": "math-g2-add-sub-100",
        "grade": 2,
        "subject": "数学",
        "explanation": "对齐才能正确相加减。",
    },
    "q-g2-word-01": {
        "prompt": "小明有 15 个苹果，小红比小明多 8 个，小红有几个？",
        "answer": "23",
        "knowledge_point_id": "kp-g2-word-problem-more-less",
        "unit_id": "math-g2-add-sub-100",
        "grade": 2,
        "subject": "数学",
        "explanation": "比…多 → 加法 15+8=23。",
    },
    "q-g2-nocarry-01": {
        "prompt": "23 + 14 = ?",
        "answer": "37",
        "knowledge_point_id": "kp-g2-add-no-carry",
        "unit_id": "math-g2-add-sub-100",
        "grade": 2,
        "subject": "数学",
        "explanation": "不进位加法。",
    },
    "q-g2-mult-01": {
        "prompt": "3 × 4 = ?",
        "answer": "12",
        "knowledge_point_id": "kp-g2-mult-meaning",
        "unit_id": "math-g2-multiply-table-2-5",
        "grade": 2,
        "subject": "数学",
        "explanation": "3 个 4 相加等于 12。",
    },
    "q-g2-carry-03": {"prompt": "58 + 27 = ?", "answer": "85", "knowledge_point_id": "kp-g2-add-carry", "unit_id": "math-g2-add-sub-100", "grade": 2, "subject": "数学", "explanation": "进位加法。"},
    "q-g2-carry-04": {"prompt": "69 + 15 = ?", "answer": "84", "knowledge_point_id": "kp-g2-add-carry", "unit_id": "math-g2-add-sub-100", "grade": 2, "subject": "数学", "explanation": "个位满十进 1。"},
    "q-g2-carry-05": {"prompt": "47 + 36 = ?", "answer": "83", "knowledge_point_id": "kp-g2-add-carry", "unit_id": "math-g2-add-sub-100", "grade": 2, "subject": "数学", "explanation": "进位加法。"},
    "q-g2-borrow-03": {"prompt": "81 - 56 = ?", "answer": "25", "knowledge_point_id": "kp-g2-sub-borrow", "unit_id": "math-g2-add-sub-100", "grade": 2, "subject": "数学", "explanation": "退位减法。"},
    "q-g2-borrow-04": {"prompt": "70 - 38 = ?", "answer": "32", "knowledge_point_id": "kp-g2-sub-borrow", "unit_id": "math-g2-add-sub-100", "grade": 2, "subject": "数学", "explanation": "个位不够减向十位借 1。"},
    "q-g2-borrow-05": {"prompt": "54 - 29 = ?", "answer": "25", "knowledge_point_id": "kp-g2-sub-borrow", "unit_id": "math-g2-add-sub-100", "grade": 2, "subject": "数学", "explanation": "退位减法。"},
    "q-g2-nocarry-02": {"prompt": "34 + 22 = ?", "answer": "56", "knowledge_point_id": "kp-g2-add-no-carry", "unit_id": "math-g2-add-sub-100", "grade": 2, "subject": "数学", "explanation": "不进位加法。"},
    "q-g2-nocarry-03": {"prompt": "61 + 18 = ?", "answer": "79", "knowledge_point_id": "kp-g2-add-no-carry", "unit_id": "math-g2-add-sub-100", "grade": 2, "subject": "数学", "explanation": "不进位加法。"},
    "q-g2-noborrow-01": {"prompt": "78 - 35 = ?", "answer": "43", "knowledge_point_id": "kp-g2-sub-no-borrow", "unit_id": "math-g2-add-sub-100", "grade": 2, "subject": "数学", "explanation": "不退位减法。"},
    "q-g2-noborrow-02": {"prompt": "96 - 44 = ?", "answer": "52", "knowledge_point_id": "kp-g2-sub-no-borrow", "unit_id": "math-g2-add-sub-100", "grade": 2, "subject": "数学", "explanation": "不退位减法。"},
    "q-g2-chain-01": {"prompt": "15 + 8 + 12 = ?", "answer": "35", "knowledge_point_id": "kp-g2-add-sub-chain", "unit_id": "math-g2-add-sub-100", "grade": 2, "subject": "数学", "explanation": "连加从左到右。"},
    "q-g2-chain-02": {"prompt": "50 - 12 - 8 = ?", "answer": "30", "knowledge_point_id": "kp-g2-add-sub-chain", "unit_id": "math-g2-add-sub-100", "grade": 2, "subject": "数学", "explanation": "连减从左到右。"},
    "q-g2-mixed-01": {"prompt": "36 + 24 - 18 = ?", "answer": "42", "knowledge_point_id": "kp-g2-add-sub-mixed", "unit_id": "math-g2-add-sub-100", "grade": 2, "subject": "数学", "explanation": "加减混合从左到右。"},
    "q-g2-mixed-02": {"prompt": "45 - 17 + 9 = ?", "answer": "37", "knowledge_point_id": "kp-g2-add-sub-mixed", "unit_id": "math-g2-add-sub-100", "grade": 2, "subject": "数学", "explanation": "加减混合。"},
    "q-g2-word-02": {"prompt": "小华有 20 本书，小丽比小华少 7 本，小丽有几本？", "answer": "13", "knowledge_point_id": "kp-g2-word-problem-more-less", "unit_id": "math-g2-add-sub-100", "grade": 2, "subject": "数学", "explanation": "比…少 → 减法。"},
    "q-g2-word-03": {"prompt": "篮子里有 18 个苹果，又放进 9 个，现在有几个？", "answer": "27", "knowledge_point_id": "kp-g2-word-problem-more-less", "unit_id": "math-g2-add-sub-100", "grade": 2, "subject": "数学", "explanation": "增加用加法。"},
    "q-g2-align-02": {"prompt": "竖式计算 45+38 时，5 应该和哪个数字对齐？", "answer": "8", "knowledge_point_id": "kp-g2-align-digits", "unit_id": "math-g2-add-sub-100", "grade": 2, "subject": "数学", "explanation": "个位对个位。"},
    "q-g2-mult-02": {"prompt": "5 × 3 = ?", "answer": "15", "knowledge_point_id": "kp-g2-mult-meaning", "unit_id": "math-g2-multiply-table-2-5", "grade": 2, "subject": "数学", "explanation": "5 个 3 相加。"},
    "q-g2-mult-03": {"prompt": "2 × 7 = ?", "answer": "14", "knowledge_point_id": "kp-g2-mult-table-2", "unit_id": "math-g2-multiply-table-2-5", "grade": 2, "subject": "数学", "explanation": "2 的乘法口诀。"},
    "q-g2-mult-04": {"prompt": "5 × 6 = ?", "answer": "30", "knowledge_point_id": "kp-g2-mult-table-5", "unit_id": "math-g2-multiply-table-2-5", "grade": 2, "subject": "数学", "explanation": "5 的乘法口诀。"},
    "q-g2-mult-word-01": {"prompt": "每盒有 4 支铅笔，买了 3 盒，一共有几支？", "answer": "12", "knowledge_point_id": "kp-g2-mult-word-problem", "unit_id": "math-g2-multiply-table-2-5", "grade": 2, "subject": "数学", "explanation": "3×4=12。"},
    "q-cn-punct-01": {"prompt": "「今天天气真好」句末应该用什么标点？", "answer": "。", "knowledge_point_id": "kp-g2-punct-period", "unit_id": "chinese-g2-sentence-basic", "grade": 2, "subject": "语文", "explanation": "陈述句用句号。"},
    "q-cn-punct-02": {"prompt": "「你叫什么名字」句末应该用什么标点？", "answer": "？", "knowledge_point_id": "kp-g2-punct-question", "unit_id": "chinese-g2-sentence-basic", "grade": 2, "subject": "语文", "explanation": "疑问句用问号。"},
    "q-cn-punct-03": {"prompt": "「太棒了」句末应该用什么标点？", "answer": "！", "knowledge_point_id": "kp-g2-punct-exclaim", "unit_id": "chinese-g2-sentence-basic", "grade": 2, "subject": "语文", "explanation": "感叹句用感叹号。"},
    "q-cn-order-01": {"prompt": "把词语排成句子：我 学校 去 。", "answer": "我去学校", "knowledge_point_id": "kp-g2-word-order", "unit_id": "chinese-g2-sentence-basic", "grade": 2, "subject": "语文", "explanation": "主谓宾顺序。"},
    "q-cn-complete-01": {"prompt": "「在操场上。」这个句子完整吗？", "answer": "不完整", "knowledge_point_id": "kp-g2-sentence-complete", "unit_id": "chinese-g2-sentence-basic", "grade": 2, "subject": "语文", "explanation": "缺少主语。"},
}


def get_question(question_id: str) -> dict | None:
    return _BANK.get(question_id)


def question_public(question_id: str) -> QuestionPublic | None:
    q = get_question(question_id)
    if not q:
        return None
    return QuestionPublic(
        question_id=question_id,
        prompt=q["prompt"],
        knowledge_point_id=q["knowledge_point_id"],
        unit_id=q["unit_id"],
        grade=q["grade"],
        subject=q["subject"],
    )


def suggest_questions(
    *,
    kp_ids: list[str] | None = None,
    grade: int | None = None,
    subject: str | None = None,
    count: int = 3,
    exclude_ids: set[str] | None = None,
) -> list[QuestionPublic]:
    exclude = exclude_ids or set()
    out: list[QuestionPublic] = []
    for qid, q in _BANK.items():
        if qid in exclude:
            continue
        if kp_ids and q["knowledge_point_id"] not in kp_ids:
            continue
        if grade is not None and q["grade"] != grade:
            continue
        if subject and q["subject"] != subject:
            continue
        pub = question_public(qid)
        if pub:
            out.append(pub)
        if len(out) >= count:
            break
    return out


def grade_answer(question_id: str, answer: str) -> tuple[bool, str, dict]:
    q = get_question(question_id)
    if not q:
        raise KeyError(f"未知题目: {question_id}")
    correct = str(q["answer"]).strip()
    given = str(answer).strip()
    ok = given == correct or given.replace(" ", "") == correct.replace(" ", "")
    return ok, q["explanation"], q
