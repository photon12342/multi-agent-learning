"""Supervisor — 监督模式。

Worker Agent 执行任务并输出 JSON 分析报告，
Supervisor Agent 对输出进行质量审核（准确性/深度/格式）。
未通过时携带反馈重做，最多 max_retries 轮。
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

# 将项目根目录加入 sys.path，确保能导入 workflows
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from workflows.model_client import chat, chat_json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------

WORKER_SYSTEM = """你是一个分析助手。

请根据用户任务输出 JSON 格式的分析报告，包含以下字段：
- summary: 简要总结
- details: 详细分析
- conclusion: 结论

只返回 JSON，不要有其他输出。"""

SUPERVISOR_SYSTEM = """你是一个质量审核员。

请对用户提交的分析报告进行评分，从以下三个维度打分（1-10分）：
- accuracy: 准确性
- depth: 深度
- format: 格式规范性

取三个维度的平均分（四舍五入取整）作为总分。

如果总分 >= 7，passed 为 true，否则为 false。

返回 JSON 格式：
{"passed": true/false, "score": 总分, "feedback": "改进建议（含各维度得分）"}

只返回 JSON，不要有其他输出。"""


# ---------------------------------------------------------------------------
# Agent 调用
# ---------------------------------------------------------------------------

def run_worker(task: str, feedback: str | None = None) -> dict:
    """运行 Worker Agent，返回分析报告（dict）。"""
    prompt = task
    if feedback:
        prompt = f"{task}\n\n上次的审核反馈：{feedback}\n请根据反馈改进你的分析。"
    return chat_json(prompt, system=WORKER_SYSTEM)


def run_supervisor(report: dict) -> dict:
    """运行 Supervisor Agent，返回审核结果（dict）。"""
    prompt = json.dumps(report, ensure_ascii=False, indent=2)
    return chat_json(prompt, system=SUPERVISOR_SYSTEM)


# ---------------------------------------------------------------------------
# 监督入口
# ---------------------------------------------------------------------------

def supervisor(task: str, max_retries: int = 3) -> dict:
    """监督模式入口。

    Args:
        task: 用户任务。
        max_retries: 最大重试次数（默认 3）。

    Returns:
        {
            "output": dict,       # 最终分析报告
            "attempts": int,      # 实际尝试次数
            "final_score": int,   # 最终得分
            "warning": str,       # 可选，超过重试次数时的警告
        }
    """
    attempts = 0
    feedback = None
    last_report = None
    last_score = 0
    warning = None

    while attempts < max_retries:
        attempts += 1
        logger.info("第 %d 次尝试，Worker 执行任务", attempts)

        try:
            # Worker 执行任务
            report = run_worker(task, feedback)
            last_report = report
            logger.info("Worker 输出: %s", json.dumps(report, ensure_ascii=False)[:100])

            # Supervisor 审核
            review = run_supervisor(report)
            score = review.get("score", 0)
            passed = review.get("passed", False)
            feedback = review.get("feedback", "")
            last_score = score

            logger.info("Supervisor 评分: %d, passed: %s", score, passed)

            if passed:
                return {
                    "output": report,
                    "attempts": attempts,
                    "final_score": score,
                }
        except Exception as e:
            logger.error("第 %d 次尝试失败: %s", attempts, e)
            feedback = f"上次执行出错: {e}，请重新尝试。"

    # 超过最大重试次数
    warning = f"超过最大重试次数 ({max_retries})，强制返回最后一次结果"
    logger.warning(warning)

    return {
        "output": last_report or {},
        "attempts": attempts,
        "final_score": last_score,
        "warning": warning,
    }


# ---------------------------------------------------------------------------
# 测试入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    task = "分析 RAG（检索增强生成）技术的优缺点"
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])

    print(f"\n任务: {task}")
    print("=" * 60)

    result = supervisor(task)

    print("\n结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
