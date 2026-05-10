"""workflows/planner — 采集策略规划器。

根据目标采集量动态调整采集参数、质量门槛和迭代次数。
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from workflows.state import KBState

logger = logging.getLogger(__name__)

# 三档策略配置
TIERS: dict[str, dict[str, Any]] = {
    "lite": {
        "per_source_limit": 5,
        "relevance_threshold": 0.7,
        "max_iterations": 1,
    },
    "standard": {
        "per_source_limit": 10,
        "relevance_threshold": 0.5,
        "max_iterations": 2,
    },
    "full": {
        "per_source_limit": 20,
        "relevance_threshold": 0.4,
        "max_iterations": 3,
    },
}


def plan_strategy(target_count: int | None = None) -> dict[str, Any]:
    """根据目标采集量返回策略 dict。

    Args:
        target_count: 目标采集条目数。为 None 时从环境变量
                       PLANNER_TARGET_COUNT 读取，默认 10。

    Returns:
        dict: 包含 tier, per_source_limit, relevance_threshold,
              max_iterations, rationale 等字段的策略配置。
    """
    if target_count is None:
        raw = os.environ.get("PLANNER_TARGET_COUNT", "10")
        try:
            target_count = int(raw)
        except (ValueError, TypeError):
            logger.warning("PLANNER_TARGET_COUNT 无效: %s，使用默认值 10", raw)
            target_count = 10

    if target_count < 10:
        tier_name = "lite"
        rationale = (
            "目标采集量较少（<10），降低每源上限以快速产出，"
            "提高相关性阈值保证质量，无需多次迭代。"
        )
    elif target_count < 20:
        tier_name = "standard"
        rationale = (
            "目标采集量适中（10-20），放宽相关性阈值以覆盖更多内容，"
            "允许最多 2 轮迭代修正。"
        )
    else:
        tier_name = "full"
        rationale = (
            "目标采集量大（>=20），大幅放宽阈值确保召回率，"
            "提升每源上限以加速采集，允许 3 轮完整迭代。"
        )

    config = TIERS[tier_name].copy()
    config["tier"] = tier_name
    config["target_count"] = target_count
    config["rationale"] = rationale

    return config


def planner_node(state: KBState) -> dict:
    """Planner 节点：调用 plan_strategy 并将策略注入状态。

    Returns:
        {"plan": plan_dict}
    """
    plan = plan_strategy()
    logger.info(
        "[PlannerNode] 策略: %s, 每源上限=%d, 阈值=%.1f, 迭代=%d",
        plan["tier"],
        plan["per_source_limit"],
        plan["relevance_threshold"],
        plan["max_iterations"],
    )
    logger.info("[PlannerNode] 理由: %s", plan["rationale"])
    return {"plan": plan}
