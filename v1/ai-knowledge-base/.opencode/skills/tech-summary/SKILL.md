---
name: tech-summary
description: 当需要对采集的技术内容进行深度分析总结时使用此技能
allowed-tools:
  - Read
  - Grep
  - Glob
  - WebFetch
---

# Tech Summary 深度分析技能

## 使用场景

- 对 GitHub Trending 或其他渠道采集的原始数据进行深度分析
- 从项目列表中提炼技术趋势、共同主题、新兴概念
- 生成结构化的分析报告供知识库归档

## 执行步骤

### 步骤 1：读取最新采集文件

从 `knowledge/raw/` 目录中按文件名排序，取最新的 JSON 采集文件。

```bash
# 查找最新文件
ls -t knowledge/raw/github-trending-*.json | head -1
```

解析 JSON，提取 `items` 数组作为分析对象。

### 步骤 2：逐条深度分析

对每条项目执行以下分析：

| 维度 | 要求 |
|------|------|
| 摘要 | 中文，不超过 50 字，提炼核心价值 |
| 技术亮点 | 2-3 个，用事实和数据说话，避免空泛形容词 |
| 评分 | 1-10 整数，附简短理由 |
| 标签建议 | 3-5 个推荐标签，中英文均可 |

**评分标准**：

| 分值 | 含义 |
|------|------|
| 9-10 | 改变格局的技术或项目（新范式、里程碑级） |
| 7-8 | 直接有帮助，解决实际问题，值得投入时间 |
| 5-6 | 值得了解，有一定参考价值 |
| 1-4 | 可略过，同质化严重或价值有限 |

### 步骤 3：趋势发现

分析所有项目后，提炼：

1. **共同主题**：多个项目围绕的方向（如 Agent 框架、RAG 优化、AI 编程工具）
2. **新兴概念**：新出现但尚未成为主流的技术方向或术语
3. **生态变化**：某个框架/平台的生态活跃度变化

每条趋势需附 1-2 个佐证项目名。

### 步骤 4：输出分析结果 JSON

写入 `knowledge/analysis/tech-summary-YYYY-MM-DD.json`，格式：

```json
{
  "source": "github-trending",
  "skill": "tech-summary",
  "analyzed_at": "2025-01-01T12:00:00+08:00",
  "item_count": 15,
  "items": [
    {
      "name": "owner/repo",
      "url": "https://github.com/owner/repo",
      "summary": "不超过50字的中文核心价值摘要",
      "highlights": [
        "亮点1：用事实说话，如「上线3月获8k star」",
        "亮点2：技术特色，如「基于Rust实现零拷贝」",
        "亮点3：生态价值，如「兼容OpenAI API」"
      ],
      "score": 8,
      "score_reason": "解决了XX实际问题，技术方案新颖，社区活跃",
      "suggested_tags": ["agent", "llm", "rust"]
    }
  ],
  "trends": {
    "common_themes": [
      {"theme": "Agent 框架", "evidence": ["project-A", "project-B", "project-C"]}
    ],
    "emerging_concepts": [
      {"concept": "概念名称", "evidence": ["project-D"]}
    ],
    "ecosystem_changes": [
      {"change": "某生态活跃度上升", "evidence": ["project-E"]}
    ]
  }
}
```

## 注意事项

- **评分约束**：15 个项目中，9-10 分不超过 **2 个**，从严打分
- 技术亮点必须包含具体事实或数据，禁止纯主观描述（如"非常好"、"很强大"）
- 趋势发现至少提炼 1 条，无趋势时如实标注 `"no_significant_trend": true`
- 输出目录 `knowledge/analysis/` 不存在时自动创建
- `analyzed_at` 使用 ISO 8601 格式带时区
- 若 `items` 为空，输出 `{"items":[], "trends":{}}` 并记录 warning

## 输出格式

最终产物为 `knowledge/analysis/tech-summary-YYYY-MM-DD.json`，包含逐条深度分析结果与全局趋势发现，供知识库检索和后续技能消费。
