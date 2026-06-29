"""用户数据模型。

基于 fastapi-fullauth 的 UserMixin 扩展，增加小学生专属字段：
- display_name：昵称（小朋友怎么称呼）
- grade：年级
- phone：家长电话（可选）
"""

from __future__ import annotations

from sqlmodel import Field

from fastapi_fullauth.models.sqlmodel import RefreshTokenMixin, UserMixin


class RefreshToken(RefreshTokenMixin, table=True):
    """刷新令牌表（fastapi-fullauth 管理 token 轮换）。"""

    pass


class User(UserMixin, table=True):
    """小学生用户表。

    UserMixin 已提供：id / email / hashed_password / is_active /
    is_verified / is_superuser / created_at。
    关系（refresh_tokens）由 fastapi-fullauth 适配器通过外键管理。
    """

    display_name: str = Field(default="", max_length=100, description="昵称")
    grade: str = Field(default="", max_length=20, description="年级，如 三年级")
    phone: str = Field(default="", max_length=20, description="家长电话（可选）")
