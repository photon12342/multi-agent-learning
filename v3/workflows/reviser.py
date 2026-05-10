"""workflows/reviser — Reviewer 反馈驱动的修正节点。

读取 state["analyses"] 和 state["review_feedback"]，
调用 LLM 根据反馈修正 analyses，temperature=0.4 允许创造性改写。
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from workflows.model_client import chat_json
from workflows.nodes import accumulate_usage
from workflows.state import KBState

logger = logging.getLogger(__name__)

REVISE_SYSTEM = """你是一个知识整理专家，擅长根据审核反馈优化分析结果。
保持原意的同时改进摘要质量、技术深度、相关性、原创性和格式规范性。"""


def revise_node(state: KBState) -> dict:
    """修正节点：根据审核反馈改进 analyses。

    将 review_feedback 注入 prompt，调用 LLM 逐条修正 analyses。

    Args:
        state: 当前工作流状态。

    Returns:
        dict: {"analyses": improved_list, "cost_tracker": tracker}
              当 analyses 或 feedback 为空时返回 {}。
    """
    analyses = state.get("analyses", [])
    feedback = state.get("review_feedback", "")

    if not analyses or not feedback:
        logger.info("[ReviserNode] analyses 或 feedback 为空，跳过修正")
        return {}

    logger.info("[ReviserNode] 开始根据反馈修正 %d 条 analyses", len(analyses))

    cost_tracker = state.get("cost_tracker", {})
    node_tracker = cost_tracker.get("reviser", {})

    analyses_text = json.dumps(analyses, ensure_ascii=False, indent=2)
    prompt = f"""请根据以下审核反馈，修正知识条目分析结果。

审核反馈：
{feedback}

当前 analyses：
{analyses_text}

请逐条修正，返回完整的 analyses 列表（保持 JSON 结构一致）。
只返回 JSON 数组，不要有其他输出。"""

    try:
        result, usage = chat_json(
            prompt,
            system=REVISE_SYSTEM,
            temperature=0.4,
        )

        node_tracker = accumulate_usage(node_tracker, usage)

        # chat_json 返回 dict，如果 LLM 返回数组则包裹
        if isinstance(result, list):
            improved = result
        else:
            improved = result.get("analyses", result.get("results", []))

        if not isinstance(improved, list):
            logger.warning("[ReviserNode] LLM 返回格式异常，保留原数据")
            improved = analyses

        logger.info("[ReviserNode] 修正完成，返回 %d 条", len(improved))

        cost_tracker["reviser"] = node_tracker

        return {"analyses": improved, "cost_tracker": cost_tracker}

    except Exception as e:
        logger.error("[ReviserNode] 修正失败: %s，保留原数据", e)
        return {"analyses": analyses, "cost_tracker": cost_tracker}
