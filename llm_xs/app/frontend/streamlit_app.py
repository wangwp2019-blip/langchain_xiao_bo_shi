"""Streamlit 备用前端（零 Node 依赖）。

运行：
    streamlit run app/frontend/streamlit_app.py

通过 HTTP 调用本项目 FastAPI 后端（需先 `python run_api.py`）。
后端地址用环境变量 ``KIDS_API_BASE`` 覆盖，默认 http://127.0.0.1:8001。
鉴权开启时用 ``KIDS_API_KEY`` 注入密钥。
"""

from __future__ import annotations

import os

import requests
import streamlit as st

API_BASE = os.getenv("KIDS_API_BASE", "http://127.0.0.1:8001")
API_KEY = os.getenv("KIDS_API_KEY", "")

GRADES = ["一年级", "二年级", "三年级", "四年级", "五年级", "六年级"]
SUBJECTS = ["数学", "语文", "科学", "英语"]


def _headers() -> dict:
    return {"X-API-Key": API_KEY} if API_KEY else {}


def _post(path: str, payload: dict) -> dict:
    resp = requests.post(f"{API_BASE}{path}", json=payload, headers=_headers(), timeout=120)
    return resp.json()


def _get(path: str, params: dict | None = None) -> dict:
    resp = requests.get(f"{API_BASE}{path}", params=params, headers=_headers(), timeout=30)
    return resp.json()


st.set_page_config(page_title="小博士 · 小学生 AI 学习助手", page_icon="🌟", layout="centered")

with st.sidebar:
    st.title("🌟 小博士")
    try:
        health = _get("/api/health")
        st.success(f"模式：{health.get('mode', '?')}")
        st.caption(f"向量库：{health.get('vector_backend')} ｜ 记忆：{health.get('memory_backend')}")
        st.caption(f"鉴权：{'开' if health.get('auth_enabled') else '关'}")
    except Exception as exc:  # noqa: BLE001
        st.error(f"后端未连接：{exc}")
    st.caption(f"后端：{API_BASE}")
    user_id = st.text_input("学生 ID", value="streamlit-kid")

tab_chat, tab_quiz = st.tabs(["💬 问答", "📝 出题练习"])

with tab_chat:
    st.subheader("和小博士聊天")
    if "history" not in st.session_state:
        st.session_state.history = []
    for role, text in st.session_state.history:
        with st.chat_message(role):
            st.write(text)
    if prompt := st.chat_input("问点什么吧，比如：太阳系有几大行星？"):
        st.session_state.history.append(("user", prompt))
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            try:
                data = _post("/api/chat", {"question": prompt, "user_id": user_id, "thread_id": user_id})
                answer = data.get("answer") or data.get("error") or "(无回复)"
            except Exception as exc:  # noqa: BLE001
                answer = f"连接失败：{exc}"
            st.write(answer)
        st.session_state.history.append(("assistant", answer))

with tab_quiz:
    st.subheader("按年级出题练习")
    col1, col2, col3 = st.columns(3)
    grade = col1.selectbox("年级", GRADES, index=2)
    subject = col2.selectbox("学科", SUBJECTS, index=0)
    count = col3.number_input("题数", 1, 20, 10)

    if st.button("出题"):
        data = _post("/api/quiz", {"grade": grade, "subject": subject, "count": int(count)})
        st.session_state.quiz = data.get("quiz")

    quiz = st.session_state.get("quiz")
    if quiz:
        with st.form("answers"):
            answers = {}
            for q in quiz["questions"]:
                answers[str(q["index"])] = st.text_input(f"第{q['index']}题：{q['prompt']}", key=f"q{q['index']}")
            submitted = st.form_submit_button("提交判分")
        if submitted:
            result = _post(
                "/api/grade",
                {
                    "grade": quiz["grade"],
                    "subject": quiz["subject"],
                    "questions": quiz["questions"],
                    "answers": answers,
                },
            )
            st.metric("得分", f"{result.get('score', 0)}/100", f"答对 {result.get('correct')}/{result.get('total')}")
            st.info(result.get("summary", ""))
            for item in result.get("items", []):
                icon = "✅" if item["is_correct"] else "💪"
                st.write(f"{icon} 第{item['index']}题 {item['feedback']}")
                if not item["is_correct"]:
                    st.caption(f"正确答案：{item['correct_answer']}　{item['explanation']}")
