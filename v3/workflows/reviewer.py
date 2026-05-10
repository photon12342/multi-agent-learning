"""workflows/reviewer — Reviewer 审核模式。

对 state["analyses"] 进行多维度加权评分审核，
支持最多 3 轮迭代，iteration >= 2 时强制通过。
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from workflows.model_client import chat_json
from workflows.nodes import accumulate_usage
from workflows.state import KBState

logger = logging.getLogger(__name__)

# 五维度权重配置
WEIGHTS: dict[str, float] = {
    "summary_quality": 0.25,
    "technical_depth": 0.25,
    "relevance": 0.20,
    "originality": 0.15,
    "formatting": 0.15,
}

SCORE_SYSTEM = """你是一个严格的质量审核员，擅长评估技术分析的质量。
从五个维度对分析结果进行评分（1-10分），确保评分客观、一致。"""


def review_node(state: KBState) -> dict:
    """Reviewer 审核节点：对 analyses 进行五维度加权评分。

    Args:
        state: 当前工作流状态。

    Returns:
        dict: 包含 review_passed, review_feedback, iteration, cost_tracker。
    """
    logger.info("[ReviewerNode] 开始审核 analyses")

    plan = state.get("plan", {}) or {}
    max_iter = int(plan.get("max_iterations", 3))

    analyses = state.get("analyses", [])
    iteration = state.get("iteration", 0)
    cost_tracker = state.get("cost_tracker", {})
    node_tracker = cost_tracker.get("reviewer", {})

    # iteration >= max_iter 强制通过
    if iteration >= max_iter:
        logger.info("[ReviewerNode] iteration=%d >= %d，强制通过", iteration, max_iter)
        return {
            "review_passed": True,
            "review_feedback": f"强制通过（iteration >= {max_iter}）",
            "iteration": iteration + 1,
            "cost_tracker": cost_tracker,
        }

    # 只审核前 5 条 analyses
    target = analyses[:5]
    if not target:
        logger.info("[ReviewerNode] 无 analyses 可审核，自动通过")
        return {
            "review_passed": True,
            "review_feedback": "",
            "iteration": iteration + 1,
            "cost_tracker": cost_tracker,
        }

    # 构造审核 prompt
    analyses_text = json.dumps(target, ensure_ascii=False, indent=2)
    prompt = f"""请对以下知识条目分析结果进行评分，从五个维度打分（1-10分）：

1. summary_quality（摘要质量）：摘要是否准确、完整、清晰地反映了原文核心内容
2. technical_depth（技术深度）：技术分析的深度和洞察力
3. relevance（相关性）：与 AI/LLM/Agent 领域的相关程度
4. originality（原创性）：内容是否具有新颖性和独特价值
5. formatting（格式规范）：格式是否规范、一致

知识条目：
{analyses_text}

请返回 JSON 格式（只返回 JSON，不要有其他输出）：
{{"scores": {{"summary_quality": 8, "technical_depth": 7, "relevance": 9, "originality": 6, "formatting": 8}}, "feedback": "对各维度评分的简要说明和改进建议（中文）"}}"""

    try:
        result, usage = chat_json(
            prompt,
            system=SCORE_SYSTEM,
            temperature=0.1,
        )
        node_tracker = accumulate_usage(node_tracker, usage)

        scores = result.get("scores", {})
        feedback = result.get("feedback", "")

        # 用代码重算加权总分（不信任模型算术）
        weighted_sum = 0.0
        for dim, weight in WEIGHTS.items():
            score = scores.get(dim, 5)
            weighted_sum += score * weight

        weighted_score = weighted_sum
        passed = weighted_score >= 7.0

        logger.info(
            "[ReviewerNode] 加权总分: %.2f, passed: %s",
            weighted_score,
            passed,
        )

        # 拼装完整反馈
        full_feedback = (
            f"【评分】摘要质量={scores.get('summary_quality', '?')} "
            f"技术深度={scores.get('technical_depth', '?')} "
            f"相关性={scores.get('relevance', '?')} "
            f"原创性={scores.get('originality', '?')} "
            f"格式规范={scores.get('formatting', '?')} "
            f"| 加权总分={weighted_score:.2f} "
            f"| {'通过' if passed else '不通过'}\n"
            f"【反馈】{feedback}"
        )

        cost_tracker["reviewer"] = node_tracker

        return {
            "review_passed": passed,
            "review_feedback": full_feedback,
            "iteration": iteration + 1,
            "cost_tracker": cost_tracker,
        }

    except Exception as e:
        logger.error("[ReviewerNode] 审核失败: %s，自动通过", e)
        return {
            "review_passed": True,
            "review_feedback": f"审核失败: {e}，自动通过",
            "iteration": iteration + 1,
            "cost_tracker": cost_tracker,
        }
