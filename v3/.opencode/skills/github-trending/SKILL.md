---
name: github-trending
description: 当需要采集 GitHub 热门开源项目时使用此技能
allowed-tools:
  - Read
  - Grep
  - Glob
  - WebFetch
---

# GitHub Trending 采集技能

## 使用场景

- 需要了解近期 GitHub 热门开源项目动态时
- 日常知识库更新，收集 AI/LLM/Agent 领域优质项目
- 竞品/技术趋势分析

## 执行步骤

### 步骤 1：搜索热门仓库

调用 GitHub API 获取 trending 仓库列表。

```bash
# 获取今日 trending（按语言过滤）
GET https://api.github.com/search/repositories?q=created:>YYYY-MM-DD&sort=stars&order=desc&per_page=100
```

同时抓取 GitHub Trending 页面补充数据。

### 步骤 2：提取信息

从每个仓库提取以下字段：

| 字段 | 来源 |
|------|------|
| name | full_name |
| url | html_url |
| description | description |
| stars | stargazers_count |
| language | language |
| topics | topics |

### 步骤 3：过滤

**纳入条件**（满足任一即可）：
- 与 AI/LLM/Agent/大模型/智能体 相关
- 主题标签含 `ai`、`llm`、`machine-learning`、`deep-learning`、`agent`、`gpt`、`chatgpt`、`rag`、`langchain`
- 仓库描述含上述关键词
- 垂直领域的 AI 工具（AI+医疗、AI+编程、AI+设计 等）

**排除条件**（满足任一则跳过）：
- Awesome 列表（name/description 含 `awesome`，或 topics 含 `awesome-list`）
- 非中文用户不需要的纯本地化项目（如仅韩文/日文 non-AI 项目）

### 步骤 4：去重

以 `name`（owner/repo）为唯一键去重。同一仓库多次出现只保留一次。

### 步骤 5：撰写中文摘要

每条摘要使用固定公式：

> **{项目名}**：{一句话说明做什么}。{一句话说明为什么值得关注，突出亮点如增速快、技术新颖、生态好}。

要求：
- 中文，简洁，20-40 字
- 突出 "为什么值得关注"（增速、新颖度、生态、大厂背书等）
- 不堆砌形容词，言之有物

### 步骤 6：排序取 Top 15

按 `stars` 降序排列，取前 15 条。若 stars 接近（差距 < 5%），参考 `stars` 增速排序。

### 步骤 7：输出 JSON

写入 `knowledge/raw/github-trending-YYYY-MM-DD.json`，格式：

```json
{
  "source": "github-trending",
  "skill": "github-trending",
  "collected_at": "2025-01-01T12:00:00+08:00",
  "count": 15,
  "items": [
    {
      "name": "owner/repo",
      "url": "https://github.com/owner/repo",
      "summary": "项目名：做什么。为什么值得关注。",
      "stars": 12345,
      "language": "Python",
      "topics": ["ai", "llm", "agent"]
    }
  ]
}
```

## 注意事项

- GitHub API 有速率限制（未认证 60 req/h，认证后 5000 req/h），建议配置 `GITHUB_TOKEN`
- `created:>YYYY-MM-DD` 的日期取采集当日 7 天前，确保覆盖 trending 窗口
- 若 API 返回空或报错，降级抓取 `https://github.com/trending` 页面解析 HTML
- 输出目录 `knowledge/raw/` 不存在时自动创建
- 采集时间 `collected_at` 使用 ISO 8601 格式带时区
- 确保本地 `/etc/hosts` 或代理能正常访问 `api.github.com`

## 输出格式

最终产物为 `knowledge/raw/github-trending-YYYY-MM-DD.json`，内含完整的 Top 15 项目信息与中文摘要，供后续技能（如 tech-summary）做深度分析使用。
