"""鼓励反馈：答对热情表扬、答错温和引导，绝不打击。

文案随机挑选，避免千篇一律；全部为正向、适龄表达。
"""

from __future__ import annotations

import random

_CORRECT = [
    "答对啦！看得出你认真思考了，给你点赞！👍",
    "太棒了，完全正确！你真厉害～🌟",
    "正确！你的小脑袋转得真快！🎉",
    "答对了！继续保持这股认真劲儿哦～💪",
]

_WRONG = [
    "别灰心，每个高手都是这样练出来的，我们一起搞懂它～🚀",
    "没关系，错一次就离学会更近一步啦！我们看看正确思路～😊",
    "这道题有点小狡猾，我们一起再想想～🌈",
    "答错也很棒，因为你勇敢尝试了！看看正确答案吧～🌟",
]

_EMPTY = [
    "这道题好像还没写答案哦～没关系，我们看看正确思路～😊",
    "先别急，留空也没关系，跟着讲解一起学一遍吧～🌈",
]


def correct_feedback() -> str:
    return "小朋友，" + random.choice(_CORRECT)


def wrong_feedback(*, empty: bool = False) -> str:
    pool = _EMPTY if empty else _WRONG
    return "小朋友，" + random.choice(pool)


def summary_feedback(correct: int, total: int) -> str:
    """整体总结：无论得分高低都给正向鼓励。"""
    if total <= 0:
        return "小朋友，我们一起开始练习吧！🌈"
    ratio = correct / total
    if ratio >= 0.9:
        tail = "你太厉害啦，简直是小学霸！继续加油～🏆"
    elif ratio >= 0.6:
        tail = "做得很不错，再多练几道就更稳啦！💪"
    elif ratio >= 0.3:
        tail = "已经很努力啦，慢慢来，你一定会越来越好！🌈"
    else:
        tail = "勇敢完成练习就已经很棒啦！我们一题一题搞懂它～🚀"
    return f"小朋友，你答对了 {correct}/{total} 题，{tail}"
