# LLM 模型成本对比报告

> 本文档用于记录不同模型在相同任务下的 token 消耗和成本对比。
> 运行 `python pipeline/pipeline.py` 后，使用 `from pipeline.model_client import tracker; tracker.report()` 获取实际数据。

---

## 测试条件

| 项目 | 说明 |
|------|------|
| **测试日期** | YYYY-MM-DD |
| **任务类型** | 例如：GitHub 项目分析、RSS 文章摘要等 |
| **输入数据量** | X 条原始数据 |
| **分析条数** | X 条（评分 ≥ 6 分） |
| **每条平均输入 tokens** | ~XXX tokens |
| **每条平均输出 tokens** | ~XXX tokens |

---

## 模型对比

### 1. DeepSeek Chat

| 指标 | 数值 |
|------|------|
| **提供商** | deepseek |
| **模型** | deepseek-chat |
| **调用次数** | X 次 |
| **输入 tokens 总计** | XXX |
| **输出 tokens 总计** | XXX |
| **总计 tokens** | XXX |
| **输入价格** | ¥1.0 / 百万 tokens |
| **输出价格** | ¥2.0 / 百万 tokens |
| **预估成本** | ¥X.XX |

> 运行命令：`python pipeline/pipeline.py --sources github,rss --limit 20`

---

### 2. Qwen Plus（如已配置）

| 指标 | 数值 |
|------|------|
| **提供商** | qwen |
| **模型** | qwen-max |
| **调用次数** | X 次 |
| **输入 tokens 总计** | XXX |
| **输出 tokens 总计** | XXX |
| **总计 tokens** | XXX |
| **输入价格** | ¥4.0 / 百万 tokens |
| **输出价格** | ¥12.0 / 百万 tokens |
| **预估成本** | ¥X.XX |

> 运行命令：`LLM_PROVIDER=qwen python pipeline/pipeline.py --sources github,rss --limit 20`

---

### 3. OpenAI GPT-4o-mini（参考）

| 指标 | 数值 |
|------|------|
| **提供商** | openai |
| **模型** | gpt-4o-mini |
| **调用次数** | X 次 |
| **输入 tokens 总计** | XXX |
| **输出 tokens 总计** | XXX |
| **总计 tokens** | XXX |
| **输入价格** | ¥150.0 / 百万 tokens |
| **输出价格** | ¥600.0 / 百万 tokens |
| **预估成本** | ¥X.XX |

> 运行命令：`LLM_PROVIDER=openai python pipeline/pipeline.py --sources github,rss --limit 20`

---

## 成本汇总表

| 模型 | 调用次数 | 输入 tokens | 输出 tokens | 总成本（¥） | 每条成本（¥） |
|------|----------|-------------|-------------|-------------|---------------|
| DeepSeek Chat | X | XXX | XXX | X.XX | X.XX |
| Qwen Plus | X | XXX | XXX | X.XX | X.XX |
| OpenAI GPT-4o-mini | X | XXX | XXX | X.XX | X.XX |

---

## 结论

### 性价比排名

1. **🥇 DeepSeek Chat**
   - 成本最低，适合大规模自动化任务
   - 中文理解能力优秀
   - 推荐用于：日常采集分析流水线

2. **🥈 Qwen Plus**
   - 成本适中，能力均衡
   - 阿里云生态集成方便
   - 推荐用于：需要更强推理的场景

3. **🥉 OpenAI GPT-4o-mini**
   - 成本最高，但通用性强
   - 推荐用于：需要多语言支持或特殊能力

### 建议

- **默认选择**：DeepSeek Chat（¥1.0/¥2.0 价格最优）
- **大规模采集**：DeepSeek Chat（成本可控）
- **高质量分析**：根据预算选择 Qwen Plus 或继续使用 DeepSeek

---

## 如何生成数据

```bash
cd /Users/dcz4442/Documents/person/multi-agent-learning/v2

# 1. 运行流水线（DeepSeek）
python3 pipeline/pipeline.py --sources github,rss --limit 20

# 2. 查看成本报告
python3 -c "from pipeline.model_client import tracker; tracker.report()"

# 3. 切换模型再次测试
LLM_PROVIDER=qwen python3 pipeline/pipeline.py --sources github,rss --limit 20
LLM_PROVIDER=openai python3 pipeline/pipeline.py --sources github,rss --limit 20
```

---

*报告生成时间：{{ 自动填充 }}*
*下次更新：建议每次调整流水线后更新此文档*
