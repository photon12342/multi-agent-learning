# AI Knowledge Base

自动化技术情报采集与分析系统 —— 持续追踪 AI/LLM/Agent 领域的技术动态，将分散的资讯转化为结构化知识条目。

## 架构

```
┌──────────────────────────────────────────────────────────────────┐
│                       AI Knowledge Base                          │
├──────────────────────────────────────────────────────────────────┤
│                     ┌─ Supervisor ─┐                             │
│  User ─→ Router ───→│  Worker loop │──→ Response                 │
│                     └──────────────┘                             │
├──────────┬──────────┬──────────┬──────────┬─────────────────────┤
│ Step 1   │ Step 2   │ Step 3   │ Step 4   │ Patterns            │
│ 采集      │ 分析     │ 整理     │ 入库     │                     │
├──────────┼──────────┼──────────┼──────────┼─────────────────────┤
│ GitHub   │ LLM 摘要  │ 去重     │ JSON     │ Router: 意图路由    │
│ RSS      │ 评分      │ 质量门控 │ 索引更新  │ Supervisor: 质量审核 │
│ arXiv    │ 标签提取  │ 分类     │          │ Graph: 多步工作流   │
├──────────┴──────────┴──────────┴──────────┴─────────────────────┤
│                         数据流方向 →                              │
└──────────────────────────────────────────────────────────────────┘
```

## 快速开始

```bash
# 1. 安装依赖
cd v3 && pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM API Key（DeepSeek / Qwen / OpenAI）

# 3. 运行采集流水线
python pipeline/pipeline.py --limit 10

# 分段运行（采集+分析，稍后再整理+入库）
python pipeline/pipeline.py --step 1 --step 2 --limit 10
python pipeline/pipeline.py --step 3 --step 4

# 干跑模式（不调用 LLM，测试采集和流程）
python pipeline/pipeline.py --dry-run
```

输出文件位于 `knowledge/raw/`（原始/分析数据）和 `knowledge/articles/`（整理后的知识条目）。
