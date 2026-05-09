# AI 知识库 · 项目愿景 v1.0

## 要做什么

- 每天抓取 GitHub Trending 上与 AI 相关的仓库（按 topic 关键词过滤），最多 20 条
- 用 Agent 分析每条仓库，维度包括：
  - **技术类别**：打标签（如 `LLM`、`Agent`、`RAG`、`Training` 等）
  - **创新点**：1-3 句摘要说明该仓库的亮点/创新
  - **使用难度**：枚举 `beginner / intermediate / advanced`
- 输出为 JSON 格式，每条知识条目包含以下字段：
  - `repo`：仓库名 + URL
  - `description`：原始描述
  - `categories`：标签数组
  - `innovation`：创新点摘要
  - `difficulty`：使用难度
  - `date`：抓取日期
  - `rank`：当日排名

## 不做什么

- 不抓 GitHub Trending 以外的来源（不爬 HN、Product Hunt、Twitter 等）
- 不做代码级分析（只分析 README 和市场描述，不 clone 代码）
- 不生成中文内容（输入输出均为英文）
- 不提供用户系统 / Web UI（纯后端 pipeline，产物是 JSON 文件或 API）
- 不回填历史数据（只从上线日开始跑）

## 边界 & 验收（v1.0）

- 持续稳定运行 7 天无报错
- 每天成功输出 20 条 JSON，数据完整率 100%
- 随机抽 3 天数据人工评审：
  - 创新点摘要不跑偏率 > 80%
  - 难度分类准确率 > 70%

## 怎么验证

每次输出附带 `_health.json`，记录：
- 抓取数 / 分析成功率 / 平均耗时

提供 `npm run check` 脚本一键查看当前健康状态，无需登录看板。
