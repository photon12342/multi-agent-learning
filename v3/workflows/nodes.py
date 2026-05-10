"""workflows/nodes — LangGraph 工作流节点函数。

每个节点是纯函数：接收 KBState，返回 dict（部分状态更新）。
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workflows.model_client import chat, chat_json
from workflows.state import KBState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def accumulate_usage(tracker: dict, usage: dict) -> dict:
    """累加 token 用量到 tracker。

    Args:
        tracker: 现有的用量统计字典。
        usage: 新的用量字典，包含 prompt_tokens/completion_tokens/total_tokens。

    Returns:
        更新后的 tracker。
    """
    if not isinstance(tracker, dict):
        tracker = {}

    for key in ["prompt_tokens", "completion_tokens", "total_tokens"]:
        if key in usage:
            tracker[key] = tracker.get(key, 0) + usage[key]

    return tracker


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = PROJECT_ROOT / "knowledge" / "articles"


# ---------------------------------------------------------------------------
# 采集节点
# ---------------------------------------------------------------------------

def collect_node(state: KBState) -> dict:
    """采集节点：调用 GitHub Search API 采集 AI 相关仓库。"""
    logger.info("[CollectNode] 开始采集 AI 相关仓库")

    plan = state.get("plan", {}) or {}
    per_page = int(plan.get("per_source_limit", 10))

    query = "AI OR artificial intelligence OR machine learning OR deep learning"
    encoded_query = urllib.parse.quote(query)
    url = f"https://api.github.com/search/repositories?q={encoded_query}&sort=stars&order=desc&per_page={per_page}"

    sources = []
    cost_tracker = state.get("cost_tracker", {})
    if "collect" not in cost_tracker:
        cost_tracker["collect"] = {}

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        for item in data.get("items", []):
            sources.append({
                "source": "github",
                "title": item["full_name"],
                "url": item["html_url"],
                "description": item.get("description", ""),
                "stars": item["stargazers_count"],
                "language": item.get("language", ""),
                "collected_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            })

        logger.info("[CollectNode] 采集到 %d 条数据", len(sources))

    except Exception as e:
        logger.error("[CollectNode] 采集失败: %s", e)

    return {"sources": sources, "cost_tracker": cost_tracker}


# ---------------------------------------------------------------------------
# 分析节点
# ---------------------------------------------------------------------------

def analyze_node(state: KBState) -> dict:
    """分析节点：用 LLM 对每条数据生成中文摘要、标签、评分。"""
    logger.info("[AnalyzeNode] 开始分析数据")

    sources = state.get("sources", [])
    analyses = []
    cost_tracker = state.get("cost_tracker", {})
    node_tracker = cost_tracker.get("analyze", {})

    for source in sources:
        prompt = f"""请分析以下开源项目，生成中文摘要、标签和相关性评分（0-1）。

项目信息：
标题：{source.get("title", "")}
描述：{source.get("description", "")}
URL：{source.get("url", "")}
Stars：{source.get("stars", "N/A")}
语言：{source.get("language", "N/A")}

请返回 JSON 格式：
{{
  "summary": "中文摘要（100字以内）",
  "tags": ["标签1", "标签2", "标签3"],
  "relevance_score": 0.8
}}"""

        try:
            result, usage = chat_json(prompt, system="你是一个技术分析师，擅长分析开源项目。")
            node_tracker = accumulate_usage(node_tracker, usage)

            analysis = {
                "source_id": source.get("url", ""),
                "summary": result.get("summary", ""),
                "tags": result.get("tags", []),
                "relevance_score": result.get("relevance_score", 0.0),
                "analyzed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            analyses.append(analysis)

        except Exception as e:
            logger.error("[AnalyzeNode] 分析失败: %s", e)

    logger.info("[AnalyzeNode] 分析完成，共 %d 条", len(analyses))

    cost_tracker["analyze"] = node_tracker

    return {"analyses": analyses, "cost_tracker": cost_tracker}


# ---------------------------------------------------------------------------
# 整理节点
# ---------------------------------------------------------------------------

def _build_article(item: dict) -> dict:
    """将 analysis 转换为 article 格式。"""
    source_id = item.get("source_id", "")
    title = source_id.split("/")[-1] if "/" in source_id else source_id
    return {
        "id": source_id.replace("/", "-").replace(":", "-"),
        "title": title,
        "source": "github",
        "url": source_id,
        "summary": item.get("summary", ""),
        "tags": item.get("tags", []),
        "relevance_score": item.get("relevance_score", 0),
        "collected_at": item.get("analyzed_at", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")),
    }


def organize_node(state: KBState) -> dict:
    """整理节点：过滤低分条目、按 URL 去重、如有审核反馈则用 LLM 修正。"""
    logger.info("[OrganizeNode] 开始整理数据")

    plan = state.get("plan", {}) or {}
    threshold = float(plan.get("relevance_threshold", 0.5))

    analyses = state.get("analyses", [])
    iteration = state.get("iteration", 0)
    review_feedback = state.get("review_feedback", "")
    cost_tracker = state.get("cost_tracker", {})
    node_tracker = cost_tracker.get("organize", {})

    # 1. 过滤低分条目
    filtered = [a for a in analyses if a.get("relevance_score", 0) >= threshold]
    logger.info("[OrganizeNode] 过滤后剩余 %d 条（原 %d 条），阈值=%.1f", len(filtered), len(analyses), threshold)

    # 2. 按 URL 去重
    seen_urls = set()
    unique = []
    for a in filtered:
        url = a.get("source_id", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(a)

    logger.info("[OrganizeNode] 去重后剩余 %d 条", len(unique))

    # 3. 如有审核反馈，用 LLM 修正
    articles = []
    if iteration > 0 and review_feedback:
        logger.info("[OrganizeNode] 检测到审核反馈，开始修正")

        for item in unique:
            prompt = f"""根据以下审核反馈，修正知识条目。

审核反馈：
{review_feedback}

当前条目：
URL：{item.get("source_id", "")}
摘要：{item.get("summary", "")}
标签：{item.get("tags", [])}
相关性评分：{item.get("relevance_score", 0)}

请返回修正后的 JSON：
{{
  "summary": "修正后的中文摘要",
  "tags": ["修正后的标签"],
  "relevance_score": 0.8
}}"""

            try:
                result, usage = chat_json(prompt, system="你是一个知识整理专家，擅长根据反馈优化内容。")
                node_tracker = accumulate_usage(node_tracker, usage)

                article = _build_article(item)
                article["summary"] = result.get("summary", article["summary"])
                article["tags"] = result.get("tags", article["tags"])
                article["relevance_score"] = result.get("relevance_score", article["relevance_score"])
                articles.append(article)

            except Exception as e:
                logger.error("[OrganizeNode] 修正失败: %s", e)
                articles.append(_build_article(item))
    else:
        articles = [_build_article(item) for item in unique]

    logger.info("[OrganizeNode] 整理完成，共 %d 条 articles", len(articles))

    cost_tracker["organize"] = node_tracker

    return {"articles": articles, "cost_tracker": cost_tracker}


# ---------------------------------------------------------------------------
# 审核节点
# ---------------------------------------------------------------------------

def review_node(state: KBState) -> dict:
    """审核节点：LLM 四维度评分，iteration >= 2 强制通过。"""
    logger.info("[ReviewNode] 开始审核")

    articles = state.get("articles", [])
    iteration = state.get("iteration", 0)
    cost_tracker = state.get("cost_tracker", {})
    node_tracker = cost_tracker.get("review", {})

    # 如果 iteration >= 2，强制通过
    if iteration >= 2:
        logger.info("[ReviewNode] iteration=%d >= 2，强制通过", iteration)
        return {
            "review_passed": True,
            "review_feedback": "强制通过（iteration >= 2）",
            "iteration": iteration + 1,
            "cost_tracker": cost_tracker,
        }

    # 构造审核 prompt
    articles_summary = json.dumps(articles[:5], ensure_ascii=False, indent=2)
    prompt = f"""请对以下知识条目进行质量审核，从四个维度评分（1-10分）：
1. 摘要质量：摘要是否准确、完整、清晰
2. 标签准确：标签是否准确反映了内容主题
3. 分类合理：分类是否合理
4. 一致性：各条目格式是否一致

知识条目：
{articles_summary}

请返回 JSON 格式：
{{
  "passed": true,
  "overall_score": 8.5,
  "feedback": "详细反馈意见，包括各维度得分和改进建议",
  "scores": {{
    "summary_quality": 8,
    "tag_accuracy": 9,
    "category_reasonableness": 8,
    "consistency": 9
  }}
}}"""

    try:
        result, usage = chat_json(prompt, system="你是一个严格的质量审核员，擅长评估知识条目的质量。")
        node_tracker = accumulate_usage(node_tracker, usage)

        passed = result.get("passed", False)
        overall_score = result.get("overall_score", 0)
        feedback = result.get("feedback", "")

        logger.info("[ReviewNode] 审核完成，passed=%s, score=%.1f", passed, overall_score)

        cost_tracker["review"] = node_tracker

        return {
            "review_passed": passed,
            "review_feedback": feedback,
            "iteration": iteration + 1,
            "cost_tracker": cost_tracker,
        }

    except Exception as e:
        logger.error("[ReviewNode] 审核失败: %s", e)
        return {
            "review_passed": True,
            "review_feedback": f"审核失败: {e}，强制通过",
            "iteration": iteration + 1,
            "cost_tracker": cost_tracker,
        }


# ---------------------------------------------------------------------------
# 保存节点
# ---------------------------------------------------------------------------

def save_node(state: KBState) -> dict:
    """保存节点：将 articles 写入 knowledge/articles/ 目录的 JSON 文件，同时更新 index.json。"""
    logger.info("[SaveNode] 开始保存")

    articles = state.get("articles", [])
    if not articles:
        logger.warning("[SaveNode] 没有 articles 可保存")
        return {}

    # 确保目录存在
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)

    # 保存每个 article 到单独的文件
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    saved_files = []

    for article in articles:
        article_id = article.get("id", "")
        if not article_id:
            continue

        slug = article_id.replace("/", "-").replace(":", "-")[:50]
        filename = f"{today}-{slug}.json"
        filepath = ARTICLES_DIR / filename

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(article, f, ensure_ascii=False, indent=2)
            saved_files.append(filename)
        except Exception as e:
            logger.error("[SaveNode] 保存 %s 失败: %s", filename, e)

    # 更新 index.json
    index_path = ARTICLES_DIR / "index.json"
    index_data = {"articles": []}

    if index_path.exists():
        try:
            with open(index_path, encoding="utf-8") as f:
                index_data = json.load(f)
        except Exception as e:
            logger.error("[SaveNode] 读取 index.json 失败: %s", e)

    # 添加新 articles 到 index（去重）
    existing_ids = {a.get("id") for a in index_data.get("articles", [])}
    for article in articles:
        if article.get("id") not in existing_ids:
            index_data["articles"].append({
                "id": article.get("id"),
                "title": article.get("title"),
                "source": article.get("source"),
                "url": article.get("url"),
                "tags": article.get("tags", []),
                "relevance_score": article.get("relevance_score", 0),
            })

    try:
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
        logger.info("[SaveNode] 更新 index.json，共 %d 条", len(index_data["articles"]))
    except Exception as e:
        logger.error("[SaveNode] 保存 index.json 失败: %s", e)

    logger.info("[SaveNode] 保存完成，共 %d 个文件", len(saved_files))
    return {}
