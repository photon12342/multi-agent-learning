"""Router — 两层意图分类路由。

第一层：关键词快速匹配（零成本）
第二层：LLM 分类兜底（处理模糊意图）

三种意图：
- github_search：调用 GitHub Search API
- knowledge_query：从本地知识库检索
- general_chat：调用 LLM 直接回答
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from workflows.model_client import chat, chat_json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 关键词规则（第一层）
# ---------------------------------------------------------------------------

GITHUB_KEYWORDS = [
    "github", "repo", "repository", "项目", "开源",
    "stars", "forks", "代码库", "源码",
]
KNOWLEDGE_KEYWORDS = [
    "知识库", "文章", "笔记", "总结", "已整理",
    "index", "knowledge", "已收录", "之前整理",
]

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_index() -> list[dict]:
    """加载 knowledge/articles/index.json。"""
    index_path = PROJECT_ROOT / "knowledge" / "articles" / "index.json"
    if not index_path.exists():
        logger.warning("index.json 不存在: %s", index_path)
        return []
    with open(index_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("articles", [])


# ---------------------------------------------------------------------------
# 处理器函数
# ---------------------------------------------------------------------------

def handle_github_search(query: str) -> str:
    """调用 GitHub Search API 搜索仓库。"""
    encoded = urllib.parse.quote(query)
    url = f"https://api.github.com/search/repositories?q={encoded}&sort=stars&order=desc&per_page=5"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        items = data.get("items", [])[:5]
        if not items:
            return "未找到相关 GitHub 仓库。"
        lines = ["找到以下 GitHub 仓库："]
        for item in items:
            lines.append(f"- [{item['full_name']}]({item['html_url']}) ⭐{item['stargazers_count']}")
            if item.get("description"):
                lines.append(f"  {item['description']}")
        return "\n".join(lines)
    except Exception as e:
        logger.error("GitHub Search 失败: %s", e)
        return f"GitHub Search 失败: {e}"


def handle_knowledge_query(query: str) -> str:
    """从本地知识库检索相关文章。"""
    articles = _load_index()
    if not articles:
        return "知识库为空，请先运行采集流程。"

    q_lower = query.lower()
    matched = [
        a for a in articles
        if any(kw in a.get("title", "").lower() or kw in a.get("id", "").lower() for kw in q_lower.split())
    ]

    if not matched:
        return "未在知识库中找到相关内容。"

    lines = ["知识库中找到以下文章："]
    for a in matched[:5]:
        lines.append(f"- [{a.get('title', a['id'])}]({a.get('url', '')}) score={a.get('score', 'N/A')}")
    return "\n".join(lines)


def handle_general_chat(query: str) -> str:
    """调用 LLM 直接回答。"""
    text, usage = chat(query, system="你是一个有用的助手，用中文简洁回答。")
    logger.info("LLM usage: %s", usage)
    return text


# ---------------------------------------------------------------------------
# 意图分类
# ---------------------------------------------------------------------------

def _classify_by_keywords(query: str) -> str | None:
    """第一层：关键词快速匹配，返回意图或 None。"""
    q_lower = query.lower()
    if any(kw in q_lower for kw in GITHUB_KEYWORDS):
        return "github_search"
    if any(kw in q_lower for kw in KNOWLEDGE_KEYWORDS):
        return "knowledge_query"
    return None


def _classify_by_llm(query: str) -> str:
    """第二层：LLM 分类兜底。"""
    system = """你是一个意图分类器。用户会输入一个问题或请求，你需要将其分类为以下三种意图之一：
- github_search：涉及 GitHub 仓库搜索、开源项目查找
- knowledge_query：涉及已有知识库文章、已整理的内容查询
- general_chat：一般聊天、常识问答、其他

只返回意图名称，不要有任何其他输出。"""

    intent, _ = chat(query, system=system)
    intent = intent.strip().lower()

    if intent in ("github_search", "knowledge_query", "general_chat"):
        return intent
    logger.warning("LLM 返回未知意图 '%s'， fallback 到 general_chat", intent)
    return "general_chat"


def classify_intent(query: str) -> str:
    """两层意图分类：先关键词，后 LLM。"""
    intent = _classify_by_keywords(query)
    if intent:
        logger.info("关键词匹配到意图: %s", intent)
        return intent
    logger.info("关键词未匹配，使用 LLM 分类")
    return _classify_by_llm(query)


# ---------------------------------------------------------------------------
# 路由入口
# ---------------------------------------------------------------------------

HANDLERS: dict[str, Callable[[str], str]] = {
    "github_search": handle_github_search,
    "knowledge_query": handle_knowledge_query,
    "general_chat": handle_general_chat,
}


def route(query: str) -> str:
    """统一路由入口。

    Args:
        query: 用户输入。

    Returns:
        处理器返回的字符串结果。
    """
    intent = classify_intent(query)
    handler = HANDLERS.get(intent, handle_general_chat)
    logger.info("路由到 %s: %s", intent, query[:50])
    return handler(query)


# ---------------------------------------------------------------------------
# 测试入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    test_queries = [
        "搜索 GitHub 上关于 deepseek 的项目",
        "知识库里有没有关于 AI 的文章",
        "你好，今天天气怎么样？",
    ]

    for q in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {q}")
        print(f"{'='*60}")
        result = route(q)
        print(result)
