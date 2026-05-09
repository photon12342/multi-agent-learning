## Parent

[specs/agents-prd.md](../specs/agents-prd.md) — AI 知识库三 Agent PRD

## What to build

将采集从当前 Top 10 扩展到标准数据源：

1. **GitHub Trending 周榜 Top 50** — 优先 `?since=weekly`，超时降级为今日，提取 AI/LLM/Agent 相关项目，上限 50 条
2. **Hacker News** — 抓取首页，提取排名靠前的技术文章，过滤 AI 相关
3. **去重** — 跨来源相同 URL 只保留一条
4. **输出** — 合并写入 `knowledge/raw/{date}.json`，按热度降序

## Acceptance criteria

- [ ] GitHub Trending 产出 ≥ 30 条（含非 AI，仅过滤明显无关项）
- [ ] Hacker News 产出 ≥ 10 条
- [ ] 合并去重后 ≥ 30 条
- [ ] JSON 格式与现有 schema 兼容
- [ ] 单条超时不阻塞整体（单个源失败不影响其他源）

## Blocked by

#1 Pipeline 编排骨架
