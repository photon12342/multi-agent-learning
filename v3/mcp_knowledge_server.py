#!/usr/bin/env python3
"""MCP Knowledge Server — 让 AI 工具搜索本地知识库

JSON-RPC 2.0 over stdio.
用法: python mcp_knowledge_server.py
"""

import json
import os
import sys
from glob import glob
from pathlib import Path

ARTICLES_DIR = Path(__file__).resolve().parent / "knowledge" / "articles"

_protocol_version = "2024-11-05"
_server_info = {"name": "mcp-knowledge-server", "version": "1.0.0"}


def load_all_articles():
    articles = {}
    for fp in glob(str(ARTICLES_DIR / "*.json")):
        if Path(fp).stem == "index":
            continue
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                if isinstance(item, dict) and "id" in item:
                    articles[item["id"]] = item
        except (json.JSONDecodeError, OSError):
            pass
    return articles


_articles_cache = None


def get_articles():
    global _articles_cache
    if _articles_cache is None:
        _articles_cache = load_all_articles()
    return _articles_cache


def search_articles(keyword, limit=5):
    keyword_lower = keyword.lower()
    results = []
    for article in get_articles().values():
        text = (article.get("title", "") + " " + article.get("summary", "")).lower()
        if keyword_lower in text:
            results.append(article)
    results.sort(key=lambda x: x.get("score", 0) if isinstance(x.get("score"), (int, float)) else 0, reverse=True)
    return results[:limit]


def get_article(article_id):
    articles = get_articles()
    article = articles.get(article_id)
    if article is None:
        raise ValueError(f"Article not found: {article_id}")
    return article


def knowledge_stats():
    articles = get_articles()
    total = len(articles)
    source_dist = {}
    all_tags = {}
    for a in articles.values():
        src = a.get("source", "unknown")
        source_dist[src] = source_dist.get(src, 0) + 1
        for tag in a.get("tags", []):
            all_tags[tag] = all_tags.get(tag, 0) + 1
    top_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:20]
    return {
        "total_articles": total,
        "source_distribution": source_dist,
        "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
    }


def make_error(code, message, req_id=None):
    return {
        "jsonrpc": "2.0",
        "error": {"code": code, "message": message},
        "id": req_id,
    }


def make_success(result, req_id=None):
    return {"jsonrpc": "2.0", "result": result, "id": req_id}


def handle_request(req):
    req_id = req.get("id")
    method = req.get("method", "")
    params = req.get("params", {})

    if method == "initialize":
        return make_success(
            {
                "protocolVersion": _protocol_version,
                "serverInfo": _server_info,
                "capabilities": {"tools": {}},
            },
            req_id,
        )

    elif method == "tools/list":
        tools = [
            {
                "name": "search_articles",
                "description": "按关键词搜索文章标题和摘要",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string", "description": "搜索关键词"},
                        "limit": {"type": "integer", "description": "返回条数上限", "default": 5},
                    },
                    "required": ["keyword"],
                },
            },
            {
                "name": "get_article",
                "description": "按 ID 获取文章完整内容",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "article_id": {"type": "string", "description": "文章 ID"},
                    },
                    "required": ["article_id"],
                },
            },
            {
                "name": "knowledge_stats",
                "description": "返回知识库统计信息（文章总数、来源分布、热门标签）",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]
        return make_success({"tools": tools}, req_id)

    elif method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        try:
            if name == "search_articles":
                keyword = arguments.get("keyword", "")
                limit = arguments.get("limit", 5)
                result = search_articles(keyword, limit)
            elif name == "get_article":
                article_id = arguments.get("article_id", "")
                result = get_article(article_id)
            elif name == "knowledge_stats":
                result = knowledge_stats()
            else:
                return make_error(-32601, f"Tool not found: {name}", req_id)
            return make_success({"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]}, req_id)
        except ValueError as e:
            return make_error(-32000, str(e), req_id)
        except Exception as e:
            return make_error(-32603, f"Internal error: {e}", req_id)

    elif method == "notifications/initialized":
        return None

    else:
        return make_error(-32601, f"Method not found: {method}", req_id)


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            resp = make_error(-32700, "Parse error")
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            continue
        resp = handle_request(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
