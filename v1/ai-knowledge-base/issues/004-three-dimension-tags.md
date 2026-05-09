## Parent

[specs/agents-prd.md](../specs/agents-prd.md) — AI 知识库三 Agent PRD

## What to build

PRD 要求 "打 3 维度标签"，需在 analyzer 中实现三维标签体系。

**三维定义**：

| 维度 | 字段 | 可选值 | 说明 |
|------|------|--------|------|
| 领域 | `domain` | LLM / 前端 / 工程实践 / 金融科技 / 运维 / 数据 / 安全 / 其他 | 项目所属技术领域 |
| 价值类型 | `value_type` | 工具 / 教程 / 研究 / 框架 / 平台 | 项目的产出形态 |
| 成熟度 | `maturity` | experimental / growing / stable | 基于 star 增速和社区活跃度判断 |

每条分析结果在原有 `tags` 数组之外，新增 `domain`、`value_type`、`maturity` 三个字段。

**成熟度参考标准**：
- `stable`：总星数 > 10k 或日增 > 500
- `growing`：总星数 1k-10k 或日增 50-500
- `experimental`：总星数 < 1k 且日增 < 50

## Acceptance criteria

- [ ] 三维标签定义写入 analyzer.md
- [ ] 分析输出包含 domain / value_type / maturity 字段
- [ ] 成熟度判断有明确量化标准
- [ ] 与现有 tags 数组语义一致（tags 保持自由标签，三维为结构化字段）

## Blocked by

#1 Pipeline 编排骨架
#3 数据源扩展
