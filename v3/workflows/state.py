"""workflows/state — LangGraph 工作流共享状态定义。

遵循"报告式通信"原则：状态字段存储结构化摘要，而非原始数据。
"""

from __future__ import annotations

from typing import TypedDict


class KBState(TypedDict, total=False):
    """知识库流水线共享状态。

    各节点通过读写该状态实现"报告式通信"——
    传递的是已处理的结构化摘要，而非原始响应。
    """

    # 采集阶段：各数据源返回的结构化条目（已标准化字段名）
    # 每个 dict 包含：source, title, url, raw_content, collected_at 等
    sources: list[dict]

    # 分析阶段：LLM 对 sources 处理后的结构化结果
    # 每个 dict 包含：source_id, summary, tags, relevance_score, analyzed_at 等
    analyses: list[dict]

    # 整理阶段：去重、格式化后的最终知识条目
    # 每个 dict 包含：id, title, source, url, summary, tags, relevance_score, collected_at 等
    articles: list[dict]

    # 审核阶段：Supervisor 对输出的文字反馈（含各维度评分说明）
    review_feedback: str

    # 审核阶段：当前轮次是否通过质量门控（score >= 7）
    review_passed: bool

    # 审核阶段：当前已执行的审核循环次数（上限 3 次）
    iteration: int

    # plan 字段是 11-3 才加 · 本节还没有
    needs_human_review: bool # ← 新增：HumanFlag 节点设为 True
    
    # 全程追踪：各步骤的 token 用量，格式如 {"collect": {...}, "analyze": {...}, "organize": {...}}
    cost_tracker: dict

