"""小学学习域：KP 目录、学情 Gap、做题 Attempt、拍照 Inbox、家长报告。"""

from .router import kp_router, learning_router, parent_router, review_router

__all__ = ["learning_router", "parent_router", "kp_router", "review_router"]
