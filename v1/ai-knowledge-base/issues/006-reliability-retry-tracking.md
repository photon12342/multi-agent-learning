## Parent

[specs/agents-prd.md](../specs/agents-prd.md) — AI 知识库三 Agent PRD

## What to build

为 pipeline 增加容错和可观测性：

**上游失败下游处理**：
- collector 失败 → 跳过 analyzer/organizer，标记本次运行为 failed
- analyzer 失败 → 跳过 organizer，标记为 partial
- organizer 失败 → 不影响 raw 数据，标记为 partial

**Retry 策略**：
- collector 重试：WebFetch 超时后重试最多 3 次，指数退避（5s/15s/45s）
- 幂等：同一天重复运行不会创建重复数据（按 date 覆盖 raw 文件，articles 按 title+url 去重）

**进度追踪**：
- 每次运行写入 `knowledge/run-log.json`（追加模式），记录：
  - 日期、各步骤状态（success/skip/fail）、耗时、错误信息
- run-log 保留最近 30 天记录

## Acceptance criteria

- [ ] collector 失败时 analyzer/organizer 自动跳过
- [ ] collector 重试 3 次指数退避
- [ ] 同一天幂等运行不产生重复数据
- [ ] `knowledge/run-log.json` 结构完整，支持追溯
- [ ] run-log 仅保留 30 天

## Blocked by

#1 Pipeline 编排骨架
#5 定时调度
