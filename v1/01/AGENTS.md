# AGENTS.md — AI 知识库项目

## 项目定位

每天抓取 GitHub Trending 上与 AI 相关的仓库（最多 20 条，按 topic 关键词过滤），用 Agent 分析后输出为结构化 JSON。

## 数据输出格式

每条知识条目字段：

```
repo         仓库名 + URL
description  原始描述
categories   标签数组（如 ["LLM", "Agent", "RAG", "Training"]）
innovation   创新点摘要（1-3 句）
difficulty   枚举: beginner / intermediate / advanced
date         抓取日期（YYYY-MM-DD）
rank         当日排名
```

额外输出 `_health.json`，记录抓取数、分析成功率、平均耗时。

## 约束（不做什么）

- 不抓 GitHub Trending 以外的来源
- 不做代码级分析（只分析 README 和市场描述）
- 输入输出均为英文
- 纯后端 pipeline，不提供 Web UI / 用户系统
- 不回填历史数据，只从上线日开始跑

## 质量要求（验收标准）

- 持续稳定运行 7 天无报错
- 每天成功输出 20 条 JSON，数据完整率 100%
- 创新点摘要不跑偏率 > 80%
- 难度分类准确率 > 70%

## 验证方式

- 每次输出附带 `_health.json`
- 提供 `npm run check` 一键查看健康状态

## 跨会话指令

- spec 终态版位于 `v1/specs/project-vision.md`，本文件与此严格对齐
- 任何 scope 变更必须先更新 spec，再同步更新本文件
