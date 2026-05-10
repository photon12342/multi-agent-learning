#!/usr/bin/env python3
"""5-dimension quality scoring for knowledge entry JSON files.

Usage:
    python hooks/check_quality.py <json_file> [json_file2 ...]
    python hooks/check_quality.py knowledge/articles/*.json
"""

import glob
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


WEIGHTS = {
    "summary": 25,
    "depth": 25,
    "format": 20,
    "tags": 15,
    "buzzword": 15,
}
MAX_SCORE = sum(WEIGHTS.values())

STANDARD_TAGS = {
    "llm", "large-language-model", "ai-agent", "multi-agent",
    "coding-agent", "prompt-engineering", "agent-framework",
    "agent-orchestration", "reasoning", "inference", "fine-tuning",
    "local-deployment", "model-evaluation", "tokenizer",
    "cli-tool", "api-gateway", "toolchain", "research-tool", "dev-tool",
    "vscode-plugin", "open-source", "framework", "library", "benchmark",
    "dataset", "paper", "survey", "tutorial", "blog", "news", "show-hn",
    "fintech", "quantitative-trading", "nlp", "computer-vision",
    "rag", "vector-database", "embedding", "knowledge-graph",
    "github-trending", "hacker-news", "arxiv",
    "beginner", "intermediate", "advanced",
    "api", "sdk", "web-ui", "rust", "python", "typescript", "go",
    "docker", "kubernetes", "devops", "security",
}

TECH_KEYWORDS = [
    "llm", "agent", "模型", "推理", "训练", "微调", "部署",
    "transformer", "attention", "prompt", "向量", "嵌入", "embedding",
    "token", "上下文", "窗口", "多模态", "视觉", "语音",
    "代码生成", "自动编程", "工具调用", "function call",
    "rag", "检索增强", "知识库", "图谱", "链式", "工作流",
    "开源", "deepseek", "qwen", "claude", "gemini",
    "api", "mcp", "a2a", "协议",
]

CN_BUZZWORDS = [
    "赋能", "抓手", "闭环", "打通", "全链路", "底层逻辑",
    "颗粒度", "对齐", "拉通", "沉淀", "强大的", "革命性的",
]

EN_BUZZWORDS = [
    "groundbreaking", "revolutionary", "game-changing", "cutting-edge",
    "state-of-the-art", "best-in-class", "world-class", "next-generation",
    "disruptive", "paradigm-shift", "bleeding-edge", "unprecedented",
    "game-changer", "industry-leading",
]


@dataclass
class DimensionScore:
    name: str
    score: float
    max_score: int
    details: str = ""


@dataclass
class QualityReport:
    filepath: str
    entry_index: int
    title: str
    dimensions: list[DimensionScore] = field(default_factory=list)
    total: float = 0.0
    grade: str = ""


def _bar(score: float, max_val: float, width: int = 20) -> str:
    ratio = max(0.0, min(1.0, score / max_val)) if max_val > 0 else 0.0
    filled = int(ratio * width)
    return "█" * filled + "░" * (width - filled)


def _is_valid_id(val: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9_]+-\d{8}-\d{3}$", val))


def _is_valid_url(val: str) -> bool:
    return bool(re.match(r"^https?://", val))


def score_summary(entry: dict) -> DimensionScore:
    summary = str(entry.get("summary", ""))
    length = len(summary)

    if length >= 50:
        base = 20
    elif length >= 20:
        base = 12
    else:
        base = 5

    lower = summary.lower()
    found = sum(1 for kw in TECH_KEYWORDS if kw.lower() in lower)
    bonus = min(5, found)

    return DimensionScore(
        name="摘要质量",
        score=min(WEIGHTS["summary"], base + bonus),
        max_score=WEIGHTS["summary"],
        details=f"长度 {length} 字 (基础 {base}) + 关键词 {found} 个 (+{bonus})",
    )


def score_depth(entry: dict) -> DimensionScore:
    raw = entry.get("score")
    if raw is None:
        return DimensionScore("技术深度", 0, WEIGHTS["depth"], "缺少 score 字段")
    if not isinstance(raw, (int, float)):
        return DimensionScore("技术深度", 0, WEIGHTS["depth"],
                              f"score 类型错误 ({type(raw).__name__})")
    points = max(0.0, min(float(WEIGHTS["depth"]), raw * 2.5))
    return DimensionScore(
        name="技术深度",
        score=points,
        max_score=WEIGHTS["depth"],
        details=f"score={raw} → {points:.1f}/25",
    )


def score_format(entry: dict) -> DimensionScore:
    parts: list[tuple[str, bool]] = []

    _id = entry.get("id")
    if not _id or not isinstance(_id, str):
        parts.append(("id: 缺失", False))
    elif _is_valid_id(_id):
        parts.append(("id: 合规", True))
    else:
        parts.append(("id: 格式错误", False))

    title = entry.get("title")
    if title and isinstance(title, str) and title.strip():
        parts.append(("title: 存在", True))
    else:
        parts.append(("title: 缺失", False))

    url = entry.get("source_url", "")
    if not url:
        parts.append(("source_url: 缺失", False))
    elif _is_valid_url(str(url)):
        parts.append(("source_url: 合规", True))
    else:
        parts.append(("source_url: 格式错误", False))

    status = entry.get("status", "")
    if status in {"draft", "review", "published", "archived"}:
        parts.append(("status: 合规", True))
    else:
        parts.append(("status: 无效", False))

    ts_present = any(
        isinstance(entry.get(k), str) and bool(entry.get(k, "").strip())  # type: ignore[arg-type]
        for k in ("collected_at", "created_at", "date")
    )
    parts.append(("时间戳: " + ("存在" if ts_present else "缺失"), ts_present))

    ok_count = sum(1 for _, ok in parts if ok)
    points = ok_count * 4

    detail_str = ", ".join(label for label, __ in parts)

    return DimensionScore(
        name="格式规范",
        score=points,
        max_score=WEIGHTS["format"],
        details=detail_str,
    )


def score_tags(entry: dict) -> DimensionScore:
    tags = entry.get("tags")
    if not isinstance(tags, list):
        return DimensionScore("标签精度", 0, WEIGHTS["tags"], "tags 不是数组")
    if len(tags) == 0:
        return DimensionScore("标签精度", 0, WEIGHTS["tags"], "无标签")

    str_tags = [str(t) for t in tags if isinstance(t, str)]
    if not str_tags:
        return DimensionScore("标签精度", 0, WEIGHTS["tags"], "无有效字符串标签")

    standard_cnt = sum(1 for t in str_tags if t.lower() in STANDARD_TAGS)
    unknown = [t for t in str_tags if t.lower() not in STANDARD_TAGS]

    if 1 <= len(str_tags) <= 3:
        points = int(standard_cnt / len(str_tags) * WEIGHTS["tags"]) if standard_cnt > 0 else 5
    else:
        points = min(10, int(standard_cnt / len(str_tags) * 10))

    detail = f"{len(str_tags)} 个标签, {standard_cnt} 个在标准列表"
    if unknown:
        detail += f", 其他: {', '.join(unknown[:5])}"

    return DimensionScore(
        name="标签精度",
        score=points,
        max_score=WEIGHTS["tags"],
        details=detail,
    )


def score_buzzword(entry: dict) -> DimensionScore:
    title = str(entry.get("title", "") or "")
    summary = str(entry.get("summary", "") or "")
    text = f"{title} {summary}"

    found: list[str] = []
    for bw in CN_BUZZWORDS:
        if bw in text:
            found.append(bw)
    lower = text.lower()
    for bw in EN_BUZZWORDS:
        if bw.lower() in lower:
            found.append(bw)

    unique = sorted(set(found))
    deduction = len(unique) * 3
    points = max(0, WEIGHTS["buzzword"] - deduction)

    if not unique:
        detail = "未检测到空洞词"
    else:
        detail = f"检测到 {len(unique)} 个: {', '.join(unique[:8])}"

    return DimensionScore(
        name="空洞词检测",
        score=points,
        max_score=WEIGHTS["buzzword"],
        details=detail,
    )


def evaluate_entry(entry: dict, idx: int, filepath: str) -> QualityReport:
    if not isinstance(entry, dict):
        return QualityReport(
            filepath=filepath,
            entry_index=idx,
            title="(not an object)",
            total=0,
            grade="C",
        )

    title = str(entry.get("title") or "(no title)")
    dims = [
        score_summary(entry),
        score_depth(entry),
        score_format(entry),
        score_tags(entry),
        score_buzzword(entry),
    ]
    total = sum(d.score for d in dims)

    if total >= 80:
        grade = "A"
    elif total >= 60:
        grade = "B"
    else:
        grade = "C"

    return QualityReport(
        filepath=filepath,
        entry_index=idx,
        title=title[:60],
        dimensions=dims,
        total=total,
        grade=grade,
    )


def validate_file(filepath: Path) -> list[QualityReport]:
    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [QualityReport(
            filepath=str(filepath),
            entry_index=0,
            title=f"JSON parse error: {e}",
            total=0,
            grade="C",
        )]

    entries = data if isinstance(data, list) else [data]
    return [evaluate_entry(entry, i, str(filepath))
            for i, entry in enumerate(entries, 1)]


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python hooks/check_quality.py <json_file> [json_file2 ...]")
        return 1

    all_reports: list[QualityReport] = []
    any_c = False

    for pattern in sys.argv[1:]:
        matched = False
        for path_str in sorted(glob.glob(pattern)):
            matched = True
            fp = Path(path_str)
            if not fp.is_file():
                continue

            reports = validate_file(fp)
            all_reports.extend(reports)

            print(f"\n── {fp} ──")
            for r in reports:
                tb = _bar(r.total, MAX_SCORE)
                print(f"  Entry #{r.entry_index}: {r.title}")
                print(f"  [{tb}] {r.total:.0f}/{MAX_SCORE} [{r.grade}]")
                for d in r.dimensions:
                    b = _bar(d.score, d.max_score, 16)
                    print(f"    {d.name:　<6} [{b}] {d.score:.0f}/{d.max_score}")
                    if d.details:
                        print(f"            {d.details}")
                if r.grade == "C":
                    any_c = True

        if not matched:
            print(f"{pattern}: no matching files")

    print()
    n = len(all_reports)
    if n == 0:
        print("No entries found.")
        return 1

    avg = sum(r.total for r in all_reports) / n
    a = sum(1 for r in all_reports if r.grade == "A")
    b = sum(1 for r in all_reports if r.grade == "B")
    c = sum(1 for r in all_reports if r.grade == "C")

    print(f"Summary: {n} entry(ies) | Avg: {avg:.1f}/{MAX_SCORE} | "
          f"A: {a}  B: {b}  C: {c}")
    if any_c:
        print("Quality check FAILED (C-grade entries found)")
    else:
        print("Quality check PASSED")
    return 1 if any_c else 0


if __name__ == "__main__":
    sys.exit(main())
