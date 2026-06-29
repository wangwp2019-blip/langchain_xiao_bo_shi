"""认证服务入口（FastAPI + fastapi-fullauth）。

端点：
- GET  /              内嵌注册/登录页面（儿童风格）
- POST /api/v1/auth/*  fastapi-fullauth 自动注册（register/login/logout/refresh/me）
- GET  /api/health    健康检查

启动：python run.py  →  http://localhost:8002
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlmodel import SQLModel

from .auth import fullauth
from .config import CORS_ORIGINS, LLM_XS_FRONTEND_URL, LLM_XS_URL, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时建表，关闭时释放资源。"""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    await fullauth.aclose()
    await engine.dispose()


app = FastAPI(
    title="小博士 · 用户认证服务",
    description="小学生账号注册/登录，签发 JWT 供 llm_xs 大模型后端鉴权",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS：仅允许配置的前端域名跨域调用（生产收敛白名单，勿用 *）
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# 注册 fastapi-fullauth 全套路由（/api/v1/auth/*）
fullauth.init_app(app, include_routers=["auth", "profile"])


@app.get("/api/health")
async def health():
    return JSONResponse({"status": "ok", "service": "auth", "llm_xs_url": LLM_XS_URL})


@app.get("/", response_class=HTMLResponse)
async def index():
    """内嵌注册/登录页面。"""
    return HTMLResponse(_LOGIN_PAGE)


# ==================== 内嵌 HTML 页面 ====================

_LOGIN_PAGE = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>小博士 · 登录 / 注册</title>
<style>
  :root {{
    --primary: #6a8dff;
    --primary-2: #9d7bff;
    --bg-from: #a8edea;
    --bg-to: #fed6e3;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif;
    background:linear-gradient(135deg,var(--bg-from),var(--bg-to));
    background-attachment:fixed;
    min-height:100vh;
    display:flex; align-items:center; justify-content:center;
    padding:20px;
  }}
  .card {{
    background:rgba(255,255,255,0.88);
    backdrop-filter:blur(12px);
    border-radius:24px;
    box-shadow:0 20px 60px rgba(0,0,0,0.12);
    width:100%; max-width:420px;
    padding:40px 36px;
  }}
  .brand {{ text-align:center; margin-bottom:28px; }}
  .brand .logo {{ font-size:48px; }}
  .brand h1 {{ font-size:24px; color:var(--primary); margin-top:8px; }}
  .brand p {{ font-size:13px; color:#888; margin-top:4px; }}
  .tabs {{ display:flex; gap:8px; margin-bottom:24px; }}
  .tab {{
    flex:1; padding:10px; border:none; border-radius:12px;
    font-size:15px; font-weight:600; cursor:pointer;
    transition:all .2s;
  }}
  .tab.active {{
    background:linear-gradient(135deg,var(--primary),var(--primary-2));
    color:#fff; box-shadow:0 4px 12px rgba(106,141,255,.3);
  }}
  .tab:not(.active) {{ background:rgba(0,0,0,.05); color:#666; }}
  .field {{ margin-bottom:16px; }}
  .field label {{ display:block; font-size:13px; color:#555; margin-bottom:6px; }}
  .field input {{
    width:100%; padding:12px 14px; border:2px solid #e0e0e0;
    border-radius:12px; font-size:15px; outline:none;
    transition:border-color .2s, box-shadow .2s;
  }}
  .field input:focus {{
    border-color:var(--primary);
    box-shadow:0 0 0 3px rgba(106,141,255,.15);
  }}
  .btn {{
    width:100%; padding:13px; border:none; border-radius:12px;
    font-size:16px; font-weight:600; color:#fff; cursor:pointer;
    background:linear-gradient(135deg,var(--primary),var(--primary-2));
    transition:filter .2s, transform .15s;
  }}
  .btn:hover {{ filter:brightness(1.08); transform:translateY(-1px); }}
  .btn:active {{ transform:translateY(0); }}
  .btn:disabled {{ opacity:.5; cursor:not-allowed; }}
  .msg {{ text-align:center; margin-top:16px; font-size:14px; min-height:20px; }}
  .msg.ok {{ color:#16a34a; }}
  .msg.err {{ color:#ef4444; }}
  .grade-select {{ display:flex; flex-wrap:wrap; gap:6px; }}
  .grade-opt {{
    padding:6px 12px; border:2px solid #e0e0e0; border-radius:8px;
    font-size:13px; cursor:pointer; transition:all .15s;
  }}
  .grade-opt.active {{
    border-color:var(--primary); background:var(--primary); color:#fff;
  }}
  .success-box {{
    text-align:center; padding:20px 0;
  }}
  .success-box .icon {{ font-size:56px; }}
  .success-box h2 {{ color:var(--primary); margin:12px 0 8px; }}
  .success-box p {{ color:#666; font-size:14px; margin-bottom:20px; }}
  .success-box .open-btn {{
    display:inline-block; padding:12px 32px; border-radius:12px;
    background:linear-gradient(135deg,#34d399,#10b981); color:#fff;
    text-decoration:none; font-weight:600; font-size:16px;
    box-shadow:0 4px 12px rgba(16,185,129,.3);
  }}
  #grade-row {{ display:none; }}
  #name-row {{ display:none; }}
</style>
</head>
<body>
<div class="card">
  <div class="brand">
    <div class="logo">🌟</div>
    <h1>小博士 AI 学习伙伴</h1>
    <p>登录后即可和 AI 大博士聊天学习</p>
  </div>

  <div id="auth-form">
    <div class="tabs">
      <button class="tab active" id="tab-login" onclick="switchTab('login')">登录</button>
      <button class="tab" id="tab-register" onclick="switchTab('register')">注册</button>
    </div>

    <form id="form" onsubmit="return submitForm(event)">
      <div class="field" id="name-row">
        <label>昵称（小朋友怎么称呼你）</label>
        <input type="text" id="display_name" placeholder="如：小明">
      </div>
      <div class="field" id="grade-row">
        <label>年级</label>
        <div class="grade-select" id="grade-select">
          <span class="grade-opt active" data-grade="一年级">一年级</span>
          <span class="grade-opt" data-grade="二年级">二年级</span>
          <span class="grade-opt" data-grade="三年级">三年级</span>
          <span class="grade-opt" data-grade="四年级">四年级</span>
          <span class="grade-opt" data-grade="五年级">五年级</span>
          <span class="grade-opt" data-grade="六年级">六年级</span>
        </div>
      </div>
      <div class="field">
        <label>邮箱</label>
        <input type="email" id="email" placeholder="小朋友或家长的邮箱" required>
      </div>
      <div class="field">
        <label>密码</label>
        <input type="password" id="password" placeholder="至少 8 位" required>
      </div>
      <button type="submit" class="btn" id="submit-btn">登录</button>
    </form>
    <div class="msg" id="msg"></div>
  </div>

  <div id="success-box" class="success-box" style="display:none">
    <div class="icon">🎉</div>
    <h2>登录成功！</h2>
    <p>欢迎回来，<span id="welcome-name">小朋友</span>！</p>
    <a href="#" class="open-btn" id="open-kid-btn">🚀 打开小博士</a>
  </div>
</div>

<script>
const API = "/api/v1/auth";
let mode = "login";
let selectedGrade = "一年级";

function switchTab(m) {{
  mode = m;
  document.getElementById("tab-login").classList.toggle("active", m === "login");
  document.getElementById("tab-register").classList.toggle("active", m === "register");
  document.getElementById("name-row").style.display = m === "register" ? "block" : "none";
  document.getElementById("grade-row").style.display = m === "register" ? "block" : "none";
  document.getElementById("submit-btn").textContent = m === "login" ? "登录" : "注册";
  document.getElementById("msg").textContent = "";
  document.getElementById("msg").className = "msg";
}}

document.getElementById("grade-select").addEventListener("click", function(e) {{
  const opt = e.target.closest(".grade-opt");
  if (!opt) return;
  document.querySelectorAll(".grade-opt").forEach(o => o.classList.remove("active"));
  opt.classList.add("active");
  selectedGrade = opt.dataset.grade;
}});

async function submitForm(e) {{
  e.preventDefault();
  const btn = document.getElementById("submit-btn");
  const msg = document.getElementById("msg");
  btn.disabled = true;
  btn.textContent = "处理中...";
  msg.textContent = "";
  msg.className = "msg";

  const body = {{
    email: document.getElementById("email").value.trim(),
    password: document.getElementById("password").value,
  }};
  if (mode === "register") {{
    body.display_name = document.getElementById("display_name").value.trim() || body.email.split("@")[0];
    body.grade = selectedGrade;
  }}

  try {{
    const endpoint = mode === "login" ? "/login" : "/register";
    const resp = await fetch(API + endpoint, {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify(body),
    }});
    const data = await resp.json();
    if (!resp.ok) {{
      throw new Error(data.detail || data.message || "操作失败");
    }}
    // 登录/注册成功，存 token
    localStorage.setItem("kid_access_token", data.access_token);
    localStorage.setItem("kid_user", JSON.stringify(data.user));
    showSuccess(data.user);
  }} catch (err) {{
    msg.textContent = err.message;
    msg.className = "msg err";
  }} finally {{
    btn.disabled = false;
    btn.textContent = mode === "login" ? "登录" : "注册";
  }}
  return false;
}}

function showSuccess(user) {{
  document.getElementById("auth-form").style.display = "none";
  document.getElementById("success-box").style.display = "block";
  document.getElementById("welcome-name").textContent = user.display_name || user.email;
  // 读取 redirect 参数（前端守卫跳转时传入），默认用 llm_xs 前端地址
  const params = new URLSearchParams(window.location.search);
  const redirect = params.get("redirect") || "{LLM_XS_FRONTEND_URL}";
  // token 通过 URL hash 传递给前端
  const token = localStorage.getItem("kid_access_token");
  const url = redirect + (redirect.includes("#") ? "&" : "#") + "token=" + encodeURIComponent(token);
  document.getElementById("open-kid-btn").href = url;
}}

// 已登录则直接展示成功
const savedToken = localStorage.getItem("kid_access_token");
const savedUser = localStorage.getItem("kid_user");
if (savedToken && savedUser) {{
  try {{ showSuccess(JSON.parse(savedUser)); }} catch(e) {{}}
}}
</script>
</body>
</html>"""
