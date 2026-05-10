"""workflows/graph — LangGraph 工作流组装。

组装 collect → analyze → review → (organize/save) 工作流。
review 后 3 路条件路由：通过→organize，不通过且<3轮→revise，不通过且≥3轮→human_flag。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Literal
from workflows.planner import planner_node # ← 新增

# 将项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langgraph.graph import END, StateGraph

from workflows.nodes import (
    analyze_node,
    collect_node,
    organize_node,
    save_node,
)
from workflows.reviewer import review_node
from workflows.reviser import revise_node
from workflows.state import KBState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 辅助节点
# ---------------------------------------------------------------------------

def human_flag_node(state: KBState) -> dict:
    """人工介入标记节点：多次审核未通过，需要人工处理。"""
    iteration = state.get("iteration", 0)
    logger.warning("[HumanFlagNode] 审核 %d 次仍未通过，需要人工介入", iteration)
    return {}


# ---------------------------------------------------------------------------
# 路由函数
# ---------------------------------------------------------------------------

def route_after_review(state: KBState) -> str:
  """条件路由：读 state["plan"]["max_iterations"]，不再硬编码 3"""
  plan = state.get("plan", {}) or {}
  max_iter = int(plan.get("max_iterations", 3))
  iteration = state.get("iteration", 0)

  if state.get("review_passed", False):
    return "organize"
  elif iteration >= max_iter:
   return "human_flag"
  else:
   return "revise"

# ---------------------------------------------------------------------------
# 图构建
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """构建并编译 LangGraph 工作流。

    Returns:
        编译后的 StateGraph app。
    """
    graph = StateGraph(KBState)

    # 添加节点
    graph.add_node("plan", planner_node)
    graph.add_node("collect", collect_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("review", review_node)
    graph.add_node("organize", organize_node)
    graph.add_node("save", save_node)
    graph.add_node("revise", revise_node)
    graph.add_node("human_flag", human_flag_node)

    # 设置入口点
    graph.set_entry_point("plan")

    # plan → collect（规划完成后开始采集）
    graph.add_edge("plan", "collect")

    # 线性边: collect → analyze → review（review 直接审 analyses）
    graph.add_edge("collect", "analyze")
    graph.add_edge("analyze", "review")

    # 条件边: review 之后 3 路路由
    graph.add_conditional_edges(
        "review",
        route_after_review,
        {
            "organize": "organize",
            "revise": "revise",
            "human_flag": "human_flag",
        },
    )

    # organize → save → END
    graph.add_edge("organize", "save")
    graph.add_edge("save", END)

    # revise → review（修正后重新审核）
    graph.add_edge("revise", "review")

    # human_flag → END
    graph.add_edge("human_flag", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# 测试入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("构建工作流图...")
    app = build_graph()

    logger.info("开始流式执行...")
    initial_state: KBState = {
        "sources": [],
        "analyses": [],
        "articles": [],
        "review_feedback": "",
        "review_passed": False,
        "iteration": 0,
        "cost_tracker": {},
    }

    final_state = None
    for chunk in app.stream(initial_state):
        for node_name, state_update in chunk.items():
            logger.info("[Graph] 节点 %s 执行完成", node_name)

            if node_name == "collect":
                sources = state_update.get("sources", [])
                logger.info("[Graph] 采集到 %d 条数据", len(sources))
                if sources:
                    logger.info("[Graph] 第一条: %s", sources[0].get("title", ""))

            elif node_name == "analyze":
                analyses = state_update.get("analyses", [])
                logger.info("[Graph] 分析完成 %d 条", len(analyses))

            elif node_name == "review":
                passed = state_update.get("review_passed", False)
                feedback = state_update.get("review_feedback", "")
                iteration = state_update.get("iteration", 0)
                logger.info("[Graph] 审核结果: passed=%s, iteration=%d", passed, iteration)
                if feedback:
                    logger.info("[Graph] 审核反馈: %s", feedback[:100])

            elif node_name == "revise":
                analyses = state_update.get("analyses", [])
                logger.info("[Graph] 修正完成 %d 条", len(analyses))

            elif node_name == "organize":
                articles = state_update.get("articles", [])
                logger.info("[Graph] 整理完成 %d 条 articles", len(articles))

            elif node_name == "save":
                logger.info("[Graph] 保存完成")

            elif node_name == "human_flag":
                logger.info("[Graph] 标记人工介入")

            final_state = state_update

    logger.info("[Graph] 工作流执行完成")
    if final_state:
        cost_tracker = final_state.get("cost_tracker", {})
        logger.info("[Graph] Token 用量: %s", cost_tracker)
