## Parent

[specs/agents-prd.md](../specs/agents-prd.md) — AI 知识库三 Agent PRD

## What to build

PRD 说 "整理成 MD"，当前实现为 JSON。经评估，决定：

**采用 JSON 作为存储格式，MD 作为可选导出格式**。

理由：
- JSON 结构化数据便于程序消费、查询、转换
- JSON 可无损转 MD，反之不行
- 下游可能对接其他系统，JSON 兼容性更好

当前 organizer 输出的 JSON schema 保持不变（title, url, source, popularity, deep_summary, highlight, score, tags, date, created_at），新增一个可选导出步骤：将当天所有条目合并渲染为 `knowledge/articles/{date}/README.md`。

## Acceptance criteria

- [ ] JSON 存储格式确认，更新 organizer.md 明确说明
- [ ] 可选：由 organizer 或独立脚本生成当天汇总的 README.md，包含所有条目的标题、评分、摘要表格
- [ ] MD 模板统一（预留 frontmatter 头）

## Blocked by

#1 Pipeline 编排骨架
#3 数据源扩展
