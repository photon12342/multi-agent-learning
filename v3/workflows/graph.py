"""workflows/graph — LangGraph 工作流组装。

组装 collect → analyze → organize → review → (save) 工作流。
review 节点后根据 review_passed 条件分支。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Literal

# 将项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langgraph.graph import END, StateGraph

from workflows.nodes import (
    analyze_node,
    collect_node,
    organize_node,
    review_node,
    save_node,
)
from workflows.state import KBState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 路由函数
# ---------------------------------------------------------------------------

def _after_review(state: KBState) -> Literal["save", "organize"]:
    """review 节点后的路由逻辑。

    根据 review_passed 决定是保存还是重新整理。
    """
    passed = state.get("review_passed", False)
    if passed:
        logger.info("[Graph] 审核通过，进入保存节点")
        return "save"
    else:
        logger.info("[Graph] 审核未通过，回到整理节点修正")
        return "organize"


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
    graph.add_node("collect", collect_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("organize", organize_node)
    graph.add_node("review", review_node)
    graph.add_node("save", save_node)

    # 设置入口点
    graph.set_entry_point("collect")

    # 线性边: collect → analyze → organize → review
    graph.add_edge("collect", "analyze")
    graph.add_edge("analyze", "organize")
    graph.add_edge("organize", "review")

    # 条件边: review 之后根据 review_passed 分支
    graph.add_conditional_edges(
        "review",
        _after_review,
        {
            "save": "save",
            "organize": "organize",
        },
    )

    # save → END
    graph.add_edge("save", END)

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

            # 打印关键输出
            if node_name == "collect":
                sources = state_update.get("sources", [])
                logger.info("[Graph] 采集到 %d 条数据", len(sources))
                if sources:
                    logger.info("[Graph] 第一条: %s", sources[0].get("title", ""))

            elif node_name == "analyze":
                analyses = state_update.get("analyses", [])
                logger.info("[Graph] 分析完成 %d 条", len(analyses))

            elif node_name == "organize":
                articles = state_update.get("articles", [])
                logger.info("[Graph] 整理完成 %d 条 articles", len(articles))

            elif node_name == "review":
                passed = state_update.get("review_passed", False)
                feedback = state_update.get("review_feedback", "")
                iteration = state_update.get("iteration", 0)
                logger.info("[Graph] 审核结果: passed=%s, iteration=%d", passed, iteration)
                if feedback:
                    logger.info("[Graph] 审核反馈: %s", feedback[:100])

            elif node_name == "save":
                logger.info("[Graph] 保存完成")

            final_state = state_update

    logger.info("[Graph] 工作流执行完成")
    if final_state:
        cost_tracker = final_state.get("cost_tracker", {})
        logger.info("[Graph] Token 用量: %s", cost_tracker)
