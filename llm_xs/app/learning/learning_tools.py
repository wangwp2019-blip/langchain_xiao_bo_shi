"""LangGraph 学习域工具（挂载到 Agent）。"""



from __future__ import annotations



from langchain_core.tools import tool

from langgraph.prebuilt import ToolRuntime



from . import attempt_service, gap_service, photo_service, plan_service, push_queue, wiki_service

from .context_service import format_context_for_prompt

from .evolution_service import get_remediation_hint

from .kp_catalog import get_kp

from .question_bank import question_public, suggest_questions

from .schemas import FreeformAttemptRequest, PhotoClassifyRequest

from .vision_service import format_vision_for_prompt, get_session





def _uid(runtime: ToolRuntime | None) -> str:

    if runtime and runtime.config:

        cfg = runtime.config.get("configurable") or {}

        return str(cfg.get("user_id") or "default-student")

    return "default-student"





@tool(parse_docstring=True)

def query_learning_gaps(runtime: ToolRuntime) -> str:

    """查询学生当前学情漏洞（按知识点），返回有练习证据的薄弱项。



    当小朋友问「我哪里不会」「薄弱点」「学得怎么样」时使用。

    必须基于返回的真实 gap_id 回答，不可臆造。

    """

    sid = _uid(runtime)

    gaps = gap_service.list_gaps(sid)

    weak = [g for g in gaps if g.status == "weak"]

    if not weak:

        return "暂无薄弱知识点记录（还没有这方面练习记录）。"

    lines = ["当前需巩固的知识点（有练习证据）："]

    for g in weak[:5]:

        lines.append(f"- {g.title}（gap_id={g.knowledge_point_id}, 练习{g.attempt_count}次）")

    return "\n".join(lines)





@tool(parse_docstring=True)

def submit_learning_attempt(question_id: str, answer: str, runtime: ToolRuntime) -> str:

    """提交题库练习题作答并更新学情。



    Args:

        question_id: 题目 ID（先通过 suggest_learning_questions 获取）

        answer: 学生答案

    """

    sid = _uid(runtime)

    try:

        att = attempt_service.submit_bank_attempt(sid, question_id, answer)

    except Exception as exc:  # noqa: BLE001

        return f"提交失败：{exc}"

    return (

        f"attempt_id={att.attempt_id}，{'正确' if att.is_correct else '需巩固'}。"

        f"关联知识点 {att.knowledge_point_id}。{att.feedback}"

    )





@tool(parse_docstring=True)

def submit_freeform_attempt(prompt: str, student_answer: str, runtime: ToolRuntime) -> str:

    """提交真实作业题（非题库）作答，LLM 判分后纳入学情。



    Args:

        prompt: 题目内容

        student_answer: 学生答案

    """

    sid = _uid(runtime)

    att = attempt_service.submit_freeform(

        sid, FreeformAttemptRequest(prompt=prompt, student_answer=student_answer)

    )

    return (

        f"attempt_id={att.attempt_id}，{'正确' if att.is_correct else '需巩固'}，"

        f"kp={att.knowledge_point_id}。{att.feedback}"

    )





@tool(parse_docstring=True)

def suggest_learning_questions(runtime: ToolRuntime, count: int = 2) -> str:

    """按学情薄弱点推荐练习题（不含答案）。



    Args:

        count: 推荐题数，1～5

    """

    sid = _uid(runtime)

    profile = attempt_service.get_profile(sid)

    grade = profile.grade_level if profile else 2

    kp_ids = gap_service.weak_kp_ids(sid) or None

    qs = suggest_questions(kp_ids=kp_ids, grade=grade, count=min(max(count, 1), 5))

    if not qs:

        return "暂时没有合适的练习题，可以先讲解知识点。"

    lines = ["推荐练习（请用 question_get 查看题面）："]

    for q in qs:

        lines.append(f"- question_id={q.question_id} · {q.prompt}")

    return "\n".join(lines)





@tool(parse_docstring=True)

def push_queue_peek(runtime: ToolRuntime, count: int = 2) -> str:

    """查看推题队列中的待练题目（不含答案）。



    Args:

        count: 查看题数，1～5

    """

    sid = _uid(runtime)

    qs = push_queue.peek(sid, min(max(count, 1), 5))

    if not qs:

        return "推题队列为空，可先调用 suggest_learning_questions 或 rebuild。"

    lines = ["推题队列："]

    for q in qs:

        lines.append(f"- question_id={q.question_id} · {q.prompt}")

    return "\n".join(lines)





@tool(parse_docstring=True)

def question_get(question_id: str) -> str:

    """获取题目内容（不含答案）。



    Args:

        question_id: 题目 ID

    """

    q = question_public(question_id)

    if not q:

        return "题目不存在。"

    return f"第 {q.question_id} 题：{q.prompt}（知识点 {q.knowledge_point_id}）"





@tool(parse_docstring=True)

def explain_knowledge_point(kp_id: str) -> str:

    """讲解指定知识点（查 KP 目录 + Wiki）。



    Args:

        kp_id: 知识点 ID，如 kp-g2-sub-borrow

    """

    return wiki_service.explain_kp_wiki(kp_id)





@tool(parse_docstring=True)

def get_remediation_strategy(kp_id: str, runtime: ToolRuntime) -> str:

    """获取某知识点的个人补救策略（C-EVO）。



    Args:

        kp_id: 知识点 ID

    """

    sid = _uid(runtime)

    hint = get_remediation_hint(sid, kp_id)

    return hint or "我们一步一步来练这个知识点。"





@tool(parse_docstring=True)

def classify_homework_photo(text: str, runtime: ToolRuntime) -> str:

    """对拍照/OCR 文本进行归类并更新学情或进入 inbox。



    Args:

        text: OCR 或 Vision 识别出的文字

    """

    sid = _uid(runtime)

    triage, result = photo_service.classify_photo(

        sid, PhotoClassifyRequest(text=text, subject="数学")

    )

    if triage == "auto" and result:

        return f"已自动归类并记录学情（attempt）。"

    if triage == "inbox" and result:

        return f"置信度中等，已进入家长 inbox 待确认（inbox_id 已创建）。"

    return "已识别为讲解类请求，请直接答疑，不出题。"





@tool(parse_docstring=True)

def load_vision_context(vision_id: str) -> str:

    """加载 Vision 拍照会话上下文（P7 Agent 编排）。



    Args:

        vision_id: Vision 会话 ID

    """

    ctx = format_vision_for_prompt(vision_id)

    if not ctx:

        sess = get_session(vision_id)

        if not sess:

            return f"未找到 vision_id={vision_id}。"

    return ctx or "Vision 会话为空。"





@tool(parse_docstring=True)

def create_study_plan(runtime: ToolRuntime) -> str:

    """生成 20 分钟微学习计划。"""

    sid = _uid(runtime)

    plan = plan_service.generate_plan(sid)

    lines = [plan.title + "："]

    for s in plan.steps:

        lines.append(f"{s.step}. {s.title}（约{s.duration_min}分钟）")

    return "\n".join(lines)





@tool(parse_docstring=True)

def get_student_learning_context(runtime: ToolRuntime) -> str:

    """获取完整学情摘要（含 AnswerGate 规则）。"""

    return format_context_for_prompt(_uid(runtime))





def build_learning_tools() -> list:

    return [

        query_learning_gaps,

        submit_learning_attempt,

        submit_freeform_attempt,

        suggest_learning_questions,

        push_queue_peek,

        question_get,

        explain_knowledge_point,

        get_remediation_strategy,

        classify_homework_photo,

        load_vision_context,

        create_study_plan,

        get_student_learning_context,

    ]


