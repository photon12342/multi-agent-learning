## Parent

[specs/agents-prd.md](../specs/agents-prd.md) — AI 知识库三 Agent PRD

## What to build

创建 pipeline 编排脚本（shell），实现 collector → analyzer → organizer 的串行执行。这是整个系统的骨架。

执行逻辑：
1. 依次运行三个 Agent（按 collector → analyzer → organizer 顺序）
2. 每个 Agent 通过 exit code 判断是否成功
3. 若 collector 失败，跳过 analyzer 和 organizer，记录错误
4. 若 analyzer 失败，跳过 organizer
5. 所有输出写入对应日期目录

## Acceptance criteria

- [ ] 编排脚本接受日期参数，执行完整 pipeline
- [ ] 上游失败时下游自动跳过（collector 失败 → 不跑 analyzer/organizer）
- [ ] 每个步骤记录开始时间、结束时间、exit code 到 stdout/stderr
- [ ] 脚本可手动运行（`./run-pipeline.sh 2026-05-09`）

## Blocked by

None — can start immediately
