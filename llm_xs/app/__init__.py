"""小博士 - LangGraph 原生版。

基于 **显式 StateGraph** 重构的小学生 AI 学习伙伴：
- 主对话图：call_model ↔ tools（ReAct 循环）
- 学习卡片子图：retrieve_context → generate_card_json
- checkpointer（短期记忆）+ store（长期记忆）在 compile 时注入
"""

__version__ = "2.0.0"
