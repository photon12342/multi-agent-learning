## Parent

[specs/agents-prd.md](../specs/agents-prd.md) — AI 知识库三 Agent PRD

## What to build

配置 GitHub Actions schedule trigger，每天 UTC 0:00 自动触发 Pipeline 编排脚本。

## Acceptance criteria

- [ ] 配置 `.github/workflows/daily-pipeline.yml`
- [ ] 定时在 UTC 0:00 触发
- [ ] 支持手动 workflow_dispatch 触发
- [ ] 触发时调用 Pipeline 编排脚本，日期参数自动取当天

## Blocked by

None — can start immediately
