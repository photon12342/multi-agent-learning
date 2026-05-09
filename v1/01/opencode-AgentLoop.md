
# OpenCode 源码级 Agent Loop 逻辑解析

## 1. 核心定位

OpenCode 的主循环（Agent Loop）主要实现在：`packages/opencode/src/session/prompt.ts`。
它是典型的 **ReAct (Reasoning and Acting)** 架构实现，整个系统的核心驱动力是 **Session 状态机**。

## 2. 核心函数与调用链路

1. **`SessionPrompt.prompt()`**：
* **职责**：入口函数，接收用户输入。
* **动作**：调用 `createUserMessage()` 将用户指令写入持久化 Session。
* **触发**：若需要回复，则启动 `loop()` 流程。
2. **`SessionPrompt.loop()`**：
* **职责**：管理层函数。
* **动作**：初始化执行上下文（sessionID 等），并拉起 `runLoop()`。
3. **`runLoop()`**：
* **职责**：自治核心。
* **动作**：通过 `while (true)` 实现持续迭代。

---

## 3. 详细执行流程（四阶段闭环）

### 第一阶段：观察 (Observe) —— 状态检索

* **读取会话**：每一轮循环开始，首先读取 Session Messages。
* **上下文识别**：定位最近的 `user` 指令、`assistant` 回复及 `unfinished tasks`。
* **退出判断**：如果上一轮 `assistant` 正常完成且**没有**挂起的 `tool-calls`，则判定任务结束，跳出 `while` 循环。

### 第二阶段：思考 (Think) —— 上下文编织

* **资源组装**：读取当前 Agent 的 `system prompt`、`skills`（技能库）、`environment`（环境变量）以及 `model` 配置。
* **模型调用**：由 `processor.process()` 负责将历史消息转化成模型输入，驱动 LLM 产生思考流（Thought）和行动意向（Action）。

### 第三阶段：行动 (Act) —— 指令解析

* **工具注册与执行**：若模型请求工具，通过 `resolveTools()` 动态匹配并调用注册好的工具函数。
* **副作用产生**：在沙箱或指定环境中执行代码、读写文件或发起网络请求，捕获执行结果。

### 第四阶段：更新状态 (Update) —— 持久化反馈

* **写回 Session**：`processor.ts` 负责将 LLM 输出的文本、工具执行的结果、消耗的 Token 以及计费成本写回 Session 状态。
* **确定后续位**：
* `stop`：流程终止。
* `tool-calls` / `continue`：任务未完成，将最新的执行结果作为下一轮的“观察”输入，进入下一次循环。
* `compact`：触发上下文压缩逻辑。

---

## 4. 本质总结

OpenCode 的 Agent Loop 运行哲学可以概括为：

> **观察 Session 状态 (消息历史与工具反馈) → 动态组装 Context 让模型思考 (ReAct) → 执行模型请求的工具 (Tools) → 把执行结果与状态成本写回 Session → 进入下一轮循环。**

**一句话核心：** 这是一个**由状态驱动的步进器**，利用 LLM 和工具链不断消除 Session 中的任务不确定性，直到达成目标。