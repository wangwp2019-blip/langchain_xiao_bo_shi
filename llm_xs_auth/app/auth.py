"""FullAuth 实例配置。

签发 JWT（HS256），密钥与 llm_xs 共享（KIDS_JWT_SECRET），
llm_xs 验证本服务签发的 token 即可识别用户。
"""

from __future__ import annotations

from fastapi_fullauth import FullAuth, FullAuthConfig, UserSchema, CreateUserSchema
from fastapi_fullauth.adapters.sqlmodel import SQLModelAdapter

from .config import JWT_SECRET, session_maker
from .models import RefreshToken, User


class KidsUserSchema(UserSchema):
    """返回给前端的用户信息（含小学生专属字段）。"""

    display_name: str = ""
    grade: str = ""
    phone: str = ""


class KidsCreateUserSchema(CreateUserSchema):
    """注册请求体（含小学生专属字段）。"""

    display_name: str = ""
    grade: str = ""
    phone: str = ""


fullauth = FullAuth(
    adapter=SQLModelAdapter(
        session_maker=session_maker,
        user_model=User,
        refresh_token_model=RefreshToken,
        user_schema=KidsUserSchema,
        create_user_schema=KidsCreateUserSchema,
    ),
    config=FullAuthConfig(
        SECRET_KEY=JWT_SECRET,
        ACCESS_TOKEN_EXPIRE_MINUTES=720,  # 12h（半天免登录）
    ),
)
