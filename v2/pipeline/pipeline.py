"""Four-step knowledge base automation pipeline.

Steps: Collect -> Analyze -> Organize -> Save

Usage:
    python pipeline/pipeline.py --sources github,rss --limit 20
    python pipeline/pipeline.py --sources github --limit 5
    python pipeline/pipeline.py --sources rss --limit 10
    python pipeline/pipeline.py --sources github --limit 5 --dry-run
    python pipeline/pipeline.py --verbose
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml

# Ensure sibling modules are importable when running as `python pipeline/pipeline.py`
_pipeline_dir = Path(__file__).resolve().parent
if str(_pipeline_dir) not in sys.path:
    sys.path.insert(0, str(_pipeline_dir))

from model_client import create_provider, chat_with_retry  # noqa: E402

logger = logging.getLogger("pipeline")

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "knowledge" / "raw"
ARTICLES_DIR = BASE_DIR / "knowledge" / "articles"
RSS_CONFIG = BASE_DIR / "pipeline" / "rss_sources.yaml"

GITHUB_API = "https://api.github.com"


# ---------------------------------------------------------------------------
# Step 1: Collect
# ---------------------------------------------------------------------------


def collect_github(limit: int) -> list[dict[str, Any]]:
    """Collect trending AI projects from GitHub Search API.

    Args:
        limit: Max items to return.

    Returns:
        List of raw item dicts.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    query = (
        "ai+OR+llm+OR+agent+OR+machine-learning+OR+deep-learning"
        f"+created:>{since}"
    )
    url = f"{GITHUB_API}/search/repositories"
    params: dict[str, Any] = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": min(limit, 100),
    }

    token = _github_token()
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    logger.info("  → 正在查询 GitHub Trending，时间范围 %s 至今，上限 %d 条", since, limit)
    resp = httpx.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    items: list[dict[str, Any]] = []
    for repo in data.get("items", []):
        topics = repo.get("topics") or []
        desc = repo.get("description") or ""
        if _is_awesome(topics, desc):
            continue
        items.append({
            "source": "github",
            "source_name": repo["full_name"],
            "title": repo["full_name"],
            "url": repo["html_url"],
            "description": desc,
            "stars": repo.get("stargazers_count", 0),
            "language": repo.get("language"),
            "topics": topics,
            "collected_at": _now_iso(),
        })

    logger.info("  ✓ 采集到 %d 个 GitHub 项目", len(items))
    return items[:limit]


def collect_rss(limit: int) -> list[dict[str, Any]]:
    """Collect AI articles from configured RSS sources.

    Args:
        limit: Max items to return.

    Returns:
        List of raw item dicts.
    """
    if not RSS_CONFIG.exists():
        logger.warning("  ✗ RSS 配置文件不存在: %s", RSS_CONFIG)
        return []

    with open(RSS_CONFIG, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    sources = [s for s in config.get("sources", []) if s.get("enabled")]
    if not sources:
        logger.warning("  ✗ 没有启用的 RSS 源")
        return []

    items: list[dict[str, Any]] = []
    for source in sources:
        if len(items) >= limit:
            break
        logger.info("  → 正在抓取 RSS：%s", source["name"])
        try:
            resp = httpx.get(source["url"], timeout=30)
            resp.raise_for_status()
            parsed = _parse_rss(resp.text, source["name"])
            for entry in parsed:
                if len(items) >= limit:
                    break
                items.append(entry)
            logger.info("    ✓ 从「%s」获取到 %d 条", source["name"], len(parsed))
        except httpx.HTTPError as e:
            logger.warning("    ✗ 抓取「%s」失败: %s", source["name"], e)

    logger.info("  ✓ 采集到 %d 条 RSS 内容", len(items))
    return items[:limit]


def _is_awesome(topics: list[str], description: str) -> bool:
    desc_lower = description.lower()
    if "awesome" in desc_lower:
        return True
    for t in topics:
        if "awesome" in t.lower():
            return True
    return False


def _parse_rss(xml_text: str, source_name: str) -> list[dict[str, Any]]:
    """Parse RSS/Atom XML using regex (per requirement)."""
    items: list[dict[str, Any]] = []
    # Extract <item> blocks for RSS 2.0
    item_pattern = re.compile(r"<item>(.*?)</item>", re.DOTALL)
    for match in item_pattern.finditer(xml_text):
        block = match.group(1)
        title = _extract_xml_tag(block, "title")
        link = _extract_xml_tag(block, "link")
        desc = _extract_xml_tag(block, "description")
        if not title or not link:
            continue
        items.append({
            "source": "rss",
            "source_name": source_name,
            "title": _strip_html(title),
            "url": link.strip(),
            "description": _strip_html(desc) if desc else "",
            "stars": 0,
            "language": None,
            "topics": [],
            "collected_at": _now_iso(),
        })

    # Fallback: try Atom <entry> blocks
    if not items:
        entry_pattern = re.compile(r"<entry>(.*?)</entry>", re.DOTALL)
        for match in entry_pattern.finditer(xml_text):
            block = match.group(1)
            title = _extract_xml_tag(block, "title")
            link_match = re.search(r'<link[^>]*href="([^"]+)"', block)
            link = link_match.group(1) if link_match else None
            desc = _extract_xml_tag(block, "summary") or _extract_xml_tag(block, "content")
            if not title or not link:
                continue
            items.append({
                "source": "rss",
                "source_name": source_name,
                "title": _strip_html(title),
                "url": link.strip(),
                "description": _strip_html(desc) if desc else "",
                "stars": 0,
                "language": None,
                "topics": [],
                "collected_at": _now_iso(),
            })

    return items


def _extract_xml_tag(block: str, tag: str) -> str | None:
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", block, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


# ---------------------------------------------------------------------------
# Step 2: Analyze
# ---------------------------------------------------------------------------


def analyze_items(items: list[dict[str, Any]], dry_run: bool) -> list[dict[str, Any]]:
    """Enrich each item with LLM-generated summary, highlights, score, tags.

    Args:
        items: Raw collected items.
        dry_run: If True, skip LLM calls and use placeholder data.

    Returns:
        Analyzed items with extra fields.
    """
    if not items:
        return []

    analyzed: list[dict[str, Any]] = []
    provider = None if dry_run else create_provider()

    for i, item in enumerate(items):
        title = item.get("title", "?")
        digits = len(str(len(items)))
        logger.info("  [%*d/%d] 正在分析：%s", digits, i + 1, len(items), title)

        if dry_run:
            analyzed.append(_mock_analysis(item))
            continue

        prompt = _build_analysis_prompt(item)
        try:
            resp = chat_with_retry(
                provider,
                [
                    {"role": "system", "content": "你是一位技术分析师。请严格按 JSON 格式输出，不要附加任何其他文字。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            enriched = _parse_analysis(resp.content, item)
            analyzed.append(enriched)
            logger.info("    ✓ 评分 %d/10 — %s", enriched.get("score", 0), enriched.get("score_reason", ""))
        except (httpx.HTTPError, httpx.RequestError, RuntimeError) as e:
            logger.warning("    ✗ LLM 调用失败: %s", e)
            analyzed.append(_mock_analysis(item))

        time.sleep(0.5)

    if provider:
        provider.close()

    logger.info("  ✓ 分析完成：共 %d 条", len(analyzed))
    return analyzed


def _build_analysis_prompt(item: dict[str, Any]) -> str:
    title = item.get("title", "")
    desc = item.get("description", "")
    stars = item.get("stars", 0)
    lang = item.get("language") or "unknown"
    topics = ", ".join(item.get("topics", []))
    source = item.get("source", "?")

    return f"""分析以下技术内容，输出 JSON（不要任何 markdown 代码块标记）：

项目名称: {title}
来源: {source}
描述: {desc}
语言: {lang}
Stars: {stars}
标签: {topics}

请输出以下 JSON 结构（只输出 JSON，不要其他文字）：
{{
    "summary": "不超过50字的中文核心价值摘要",
    "highlights": ["亮点1（含事实数据）", "亮点2", "亮点3"],
    "score": <1-10整数，按此标准：9-10里程碑级，7-8很有价值，5-6值得了解，1-4可略过>,
    "score_reason": "评分理由（一句话）",
    "suggested_tags": ["英文小写标签", "3-5个"]
}}"""


def _parse_analysis(llm_text: str, item: dict[str, Any]) -> dict[str, Any]:
    """Parse LLM JSON response and merge with original item."""
    cleaned = llm_text.strip()
    # Strip markdown code fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("  Failed to parse LLM JSON, using fallback")
        return _mock_analysis(item)

    item["summary"] = (result.get("summary") or "")[:80]
    item["highlights"] = (result.get("highlights") or [])[:5]
    item["score"] = max(1, min(10, int(result.get("score", 5))))
    item["score_reason"] = (result.get("score_reason") or "")[:100]
    item["tags"] = (result.get("suggested_tags") or [])[:8]
    item["analyzed_at"] = _now_iso()
    return item


def _mock_analysis(item: dict[str, Any]) -> dict[str, Any]:
    item["summary"] = f"来自{item['source']}的项目，暂无分析。"
    item["highlights"] = ["需配置 API Key 后由 LLM 生成"]
    item["score"] = 5
    item["score_reason"] = "未分析，默认分数"
    item["tags"] = [item["source"]]
    item["analyzed_at"] = _now_iso()
    return item


# ---------------------------------------------------------------------------
# Step 3: Organize
# ---------------------------------------------------------------------------


def organize_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate, filter, and standardize items.

    Args:
        items: Analyzed items.

    Returns:
        Organized article dicts ready for saving.
    """
    existing_urls = _load_existing_urls()

    seen: set[str] = set()
    organized: list[dict[str, Any]] = []

    dropped = 0
    skipped = 0

    for item in items:
        url = item.get("url", "")
        score = item.get("score", 0)

        if score < 6:
            dropped += 1
            logger.info("  ✗ 评分 %d，未达 6 分门槛，丢弃：%s", score, item.get("title"))
            continue

        if url in existing_urls or url in seen:
            skipped += 1
            logger.info("  - 已存在，跳过：%s", item.get("title"))
            continue
        seen.add(url)

        slug = _make_slug(item)
        article = {
            "id": slug,
            "title": item.get("summary", item.get("title", ""))[:60],
            "source": item.get("source", "unknown"),
            "url": url,
            "collected_at": item.get("collected_at", _now_iso()),
            "summary": item.get("summary", ""),
            "highlights": item.get("highlights", []),
            "score": score,
            "score_reason": item.get("score_reason", ""),
            "tags": item.get("tags", []),
            "relevance_score": round(score / 10, 1),
        }
        organized.append(article)
        logger.info("  ✓ 通过质量门控：%s（评分 %d）", slug, score)

    if dropped:
        logger.info("  ⚠ 丢弃 %d 条（评分 < 6）", dropped)
    if skipped:
        logger.info("  - 跳过 %d 条重复内容", skipped)
    logger.info("  ✓ 整理完毕：%d 条进入保存阶段", len(organized))
    return organized


def _load_existing_urls() -> set[str]:
    """Load all URLs already in the article index."""
    index_path = ARTICLES_DIR / "index.json"
    if not index_path.exists():
        return set()
    try:
        with open(index_path, encoding="utf-8") as f:
            data = json.load(f)
        return {a["url"] for a in data.get("articles", []) if "url" in a}
    except (json.JSONDecodeError, KeyError):
        logger.warning("Failed to read index.json, assuming empty")
        return set()


def _make_slug(item: dict[str, Any]) -> str:
    """Generate a unique slug for an article."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if item.get("source") == "github":
        name = item.get("source_name") or item.get("title", "")
        if "/" in name:
            name = name.split("/")[-1]
        slug = re.sub(r"[^a-zA-Z0-9-]", "-", name).strip("-").lower()
        slug = re.sub(r"-+", "-", slug)
        return f"{today}-{slug}"

    title = item.get("title", "article")
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]", "-", title).strip("-").lower()
    slug = re.sub(r"-+", "-", slug)
    slug = slug[:40].rstrip("-")
    suffix = _short_hash(item.get("url", ""))
    return f"{today}-{slug}-{suffix}"


def _short_hash(url: str) -> str:
    return str(hash(url) % 10_000).zfill(4)


# ---------------------------------------------------------------------------
# Step 4: Save
# ---------------------------------------------------------------------------


def save_articles(articles: list[dict[str, Any]], dry_run: bool) -> None:
    """Save articles as individual JSON files and update index.

    Args:
        articles: Organized article dicts.
        dry_run: If True, log without writing.
    """
    if not articles:
        logger.info("  (无文章需要保存)")
        return

    if dry_run:
        logger.info("  [干跑模式] 以下 %d 篇文章将被保存：", len(articles))
        for a in articles:
            logger.info("    · %s（评分 %d）— %s", a["id"], a["score"], a["title"])
        return

    index_path = ARTICLES_DIR / "index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, Any] = {"updated_at": _now_iso(), "articles": []}
    if index_path.exists():
        try:
            with open(index_path, encoding="utf-8") as f:
                existing = json.load(f)
        except json.JSONDecodeError:
            pass

    existing_urls = {a["url"] for a in existing.get("articles", [])}
    saved_count = 0

    for article in articles:
        if article["url"] in existing_urls:
            logger.info("  - 索引中已存在，跳过：%s", article["id"])
            continue

        subdir = _category_dir(article.get("tags", []))
        article_dir = ARTICLES_DIR / subdir
        article_dir.mkdir(parents=True, exist_ok=True)

        file_path = article_dir / f"{article['id']}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(article, f, ensure_ascii=False, indent=2)
        saved_count += 1
        logger.info("  ✓ 已保存：%s", file_path.relative_to(BASE_DIR))

        existing["articles"].append({
            "id": article["id"],
            "title": article["title"],
            "url": article["url"],
            "score": article["score"],
            "tags": article["tags"],
        })

    existing["updated_at"] = _now_iso()
    existing["articles"].sort(key=lambda a: a["id"])

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    logger.info("  ✓ 索引已更新：%s（共 %d 条记录）",
                index_path.relative_to(BASE_DIR), len(existing["articles"]))
    logger.info("  ✓ 本次新增 %d 篇文章", saved_count)


def _category_dir(tags: list[str]) -> str:
    tag_to_dir = {
        "ai-agents": "ai-agents",
        "agent": "ai-agents",
        "llm": "llm",
        "deep-learning": "llm",
    }
    for tag in tags:
        if tag in tag_to_dir:
            return tag_to_dir[tag]
    return ARTICLES_DIR.name  # root


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _latest_file(prefix: str) -> Path | None:
    """Find the most recent file under RAW_DIR matching the given prefix."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    candidates = sorted(RAW_DIR.glob(f"{prefix}*.json"), reverse=True)
    return candidates[0] if candidates else None


def _load_json(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run_pipeline(sources: list[str], limit: int, dry_run: bool, steps: list[int] | None = None) -> None:
    """Execute the collect-analyze-organize-save pipeline.

    Args:
        sources: Source types to collect (github, rss).
        limit: Max items per source.
        dry_run: Skip LLM calls and file writes.
        steps: Which step(s) to run. Defaults to all 4 steps.
    """
    if steps is None:
        steps = [1, 2, 3, 4]
    start = time.time()
    mode = " [干跑模式]" if dry_run else ""
    step_labels = ", ".join(f"Step {s}" for s in steps)

    logger.info("")
    logger.info("=" * 56)
    logger.info("  AI 知识库自动化流水线  v2%s  [%s]", mode, step_labels)
    logger.info("=" * 56)
    logger.info("")

    today = _today_str()
    all_raw: list[dict[str, Any]] = []
    analyzed: list[dict[str, Any]] = []
    articles: list[dict[str, Any]] = []

    # -----------------------------------------------------------------------
    # Step 1: 采集
    # -----------------------------------------------------------------------
    if 1 in steps:
        logger.info("━" * 56)
        logger.info("  Step 1/4：采集数据")
        logger.info("━" * 56)

        if "github" in sources:
            all_raw.extend(collect_github(limit))
        if "rss" in sources:
            all_raw.extend(collect_rss(limit))

        if not all_raw:
            logger.warning("  ✗ 未采集到任何数据，流程终止")
            return

        raw_path = RAW_DIR / f"pipeline-raw-{today}.json"
        _save_json(raw_path, all_raw)
        logger.info("  ■ 原始数据已暂存：%s（共 %d 条）",
                    raw_path.relative_to(BASE_DIR), len(all_raw))
        logger.info("")
    elif 2 in steps or 3 in steps or 4 in steps:
        loaded = _latest_file("pipeline-raw-")
        if loaded:
            all_raw = _load_json(loaded)
            logger.info("  ■ 加载已有原始数据：%s（共 %d 条）",
                        loaded.relative_to(BASE_DIR), len(all_raw))
        else:
            logger.warning("  ✗ 未找到原始数据文件，流程终止")
            return

    # -----------------------------------------------------------------------
    # Step 2: 分析
    # -----------------------------------------------------------------------
    if 2 in steps:
        logger.info("━" * 56)
        logger.info("  Step 2/4：LLM 深度分析")
        logger.info("━" * 56)

        analyzed = analyze_items(all_raw, dry_run)

        analyzed_path = RAW_DIR / f"pipeline-analyzed-{today}.json"
        _save_json(analyzed_path, analyzed)
        logger.info("  ■ 分析结果已暂存：%s（共 %d 条）",
                    analyzed_path.relative_to(BASE_DIR), len(analyzed))
        logger.info("")
    elif 3 in steps or 4 in steps:
        loaded = _latest_file("pipeline-analyzed-")
        if loaded:
            analyzed = _load_json(loaded)
            logger.info("  ■ 加载已有分析结果：%s（共 %d 条）",
                        loaded.relative_to(BASE_DIR), len(analyzed))
        elif all_raw:
            logger.info("  ■ 跳过分析步骤，使用未分析的原始数据")
            analyzed = all_raw
        else:
            logger.info("  ■ 无分析数据，使用空列表继续")
            analyzed = []

    # -----------------------------------------------------------------------
    # Step 3: 整理
    # -----------------------------------------------------------------------
    if 3 in steps:
        logger.info("━" * 56)
        logger.info("  Step 3/4：去重 + 质量门控")
        logger.info("━" * 56)

        articles = organize_items(analyzed)
        logger.info("")

    # -----------------------------------------------------------------------
    # Step 4: 保存
    # -----------------------------------------------------------------------
    if 4 in steps:
        logger.info("━" * 56)
        logger.info("  Step 4/4：写入知识库")
        logger.info("━" * 56)

        if 3 not in steps and not articles:
            articles = organize_items(analyzed)

        save_articles(articles, dry_run)
        logger.info("")

    # -----------------------------------------------------------------------
    # 汇总
    # -----------------------------------------------------------------------
    elapsed = time.time() - start
    logger.info("=" * 56)
    logger.info("  流水线执行完毕（%.1f 秒）", elapsed)
    logger.info("  采集 %d 条 → 分析 %d 条 → 入库 %d 篇",
                len(all_raw), len(analyzed), len(articles))
    logger.info("=" * 56)
    logger.info("")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _github_token() -> str | None:
    return (os.environ.get("GITHUB_TOKEN")
            or os.environ.get("GH_TOKEN")
            or None)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI Knowledge Base — automation pipeline",
    )
    parser.add_argument(
        "--sources",
        default="github,rss",
        help="Comma-separated source list (github, rss). Default: github,rss",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max items per source. Default: 20",
    )
    parser.add_argument(
        "--step",
        type=int,
        choices=[1, 2, 3, 4],
        action="append",
        dest="steps",
        help="Run specific step(s). Can be specified multiple times, e.g. --step 1 --step 2",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate without LLM calls or file writes",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = _parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    steps = args.steps or [1, 2, 3, 4]
    run_pipeline(sources, args.limit, args.dry_run, steps=steps)


if __name__ == "__main__":
    main()
