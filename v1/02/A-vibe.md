# AGENTS.md — AI 知识库编码规范

## 技术栈

| 层 | 语言 | 运行时 | 构建/包管理器 |
|---|---|---|---|
| 后端 / Agent Pipeline | Python 3.12+ | venv / pip | uv (推荐) 或 pip-tools |
| 前端 / CLI 工具 | TypeScript 5.5+ | Node.js 22+ | pnpm |
| 数据 / 配置 | JSON / YAML | — | — |

---

## 1. Python 规范

### 1.1 风格

- 遵循 **PEP 8**，使用 **Ruff** 作为 linter + formatter（单工具）
- 行宽 **100 字符**
- 缩进 4 空格，禁止 Tab
- 文件末尾保留一个空行

### 1.2 类型标注

- **所有函数签名必须标注类型**（含 `__init__`）
- 内部变量鼓励标注，复杂类型用 `type alias`
- 使用 `typing` 或 `collections.abc`（Python 3.9+ 优先原生泛型）

```python
def fetch_trending(topics: list[str], max_count: int = 20) -> list[RepoInfo]:
    ...
```

### 1.3 导入顺序（Ruff 自动修复）

```
标准库
↓
第三方库
↓
项目内部模块
↓
类型导入（typing.TYPE_CHECKING 防护）
```

不使用 `from module import *`。

### 1.4 项目结构

```
src/
  knowledge_base/
    __init__.py
    pipeline.py       # 主流程编排
    fetcher/           # GitHub API 抓取
    analyzer/          # Agent 分析
    models/            # Pydantic 数据模型
    output/            # JSON 输出
tests/
  unit/
  integration/
```

### 1.5 数据模型

- 所有 IO 数据结构优先使用 **Pydantic v2** `BaseModel`
- 配置用 Pydantic `Settings`（环境变量 + YAML 覆盖）
- 禁止裸 dict 透传业务数据

### 1.6 异步

- IO 密集型路径必须用 `asyncio` + `httpx.AsyncClient`
- CPU 密集型任务用 `asyncio.to_thread` 或 `concurrent.futures`

---

## 2. TypeScript 规范

### 2.1 风格

- 使用 **Biome** 统一 lint + format（禁用 ESLint / Prettier）
- 行宽 **100 字符**
- 缩进 2 空格
- 末尾分号开启
- 单引号优先

### 2.2 类型

- **strict 模式**必须开启（`strict: true`）
- `any` 一票否决——用 `unknown` 代替，需要时窄化
- 优先 `interface` over `type`（对象形状），联合类型用 `type`
- 导出类型用 `interface` 命名 `XxxProps` / `XxxResult`

```typescript
interface RepoEntry {
  repo: string;
  url: string;
  description: string;
  categories: string[];
  innovation: string;
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  date: string;
  rank: number;
}
```

### 2.3 导入顺序

```
Node 内置模块
↓
第三方包
↓
项目内部模块（相对路径）
↓
类型导入（`import type`）
```

### 2.4 项目结构

```
src/
  cli/
    index.ts          # 入口
    commands/         # 子命令
  lib/
    github.ts         # API 客户端
    analyze.ts        # 分析逻辑
    output.ts         # JSON 写盘
  types/
    index.ts
tests/
```

### 2.5 运行时与打包

- 使用 `tsx` 直接运行（先编译到 `dist/` 再 `node` 跑也可以，但开发阶段用 `tsx`)
- 脚本入口不加 `.js` 后缀
- JSON 持久化用 `node:fs` 同步 API（pipeline 低频调用，简单优先）
- CLI 框架使用 **Commander** 或 **Cac**

---

## 3. 双栈共享约定

### 3.1 命名

| 范畴 | 约定 |
|---|---|
| 文件名 | `snake_case.py` / `kebab-case.ts` 或 `camelCase.ts` |
| 类名 | `PascalCase`（两栈统一） |
| 函数/方法 | `snake_case`（Python）/ `camelCase`（TS） |
| 常量 | `UPPER_SNAKE_CASE`（两栈统一） |
| 私有成员 | `_prefix`（Python）/ `#prefix` 或 `private`（TS） |

### 3.2 JSON Schema 对齐

Python Pydantic 模型与 TypeScript interface 必须 **双向可推导**。变更模型时两栈同步更新：

- 方法一：Pydantic → `model_dump()` → JSON → 消费方 TS 推断
- 方法二：使用 `pydantic-to-typescript` 或手写 interface（推荐小项目手写，显式可读）

### 3.3 错误处理

- Python: 自定义异常继承 `KnowledgeBaseError(Exception)`
- TS: 自定义 `KnowledgeBaseError extends Error`，附加 `code` 枚举字段
- 两栈错误码枚举同源（`HEALTH_CHECK_FAILED`, `FETCH_TIMEOUT`, `ANALYZE_FAILED` 等）

### 3.4 日志

- 两栈统一日志级别：`DEBUG / INFO / WARN / ERROR`
- Python 用 `loguru`（或标准库 `logging` + JSON 格式化）
- TS 用 `pino`（cli 场景）
- JSON 格式输出，供 `_health.json` 聚合消费

---

## 4. 代码质量

### 4.1 门槛

| 检查 | 工具 | 通过条件 |
|---|---|---|
| Lint | Ruff / Biome | 零 warning |
| 类型检查 | mypy (strict) / tsc --noEmit | 零 error |
| 单元测试 | pytest / vitest | 覆盖率 ≥ 80% |
| 格式化 | Ruff format / Biome check | 零 diff |

### 4.2 命令

```bash
# Python
uv run ruff check src/
uv run mypy src/
uv run pytest tests/ --cov=src

# TypeScript
pnpm biome check src/
pnpm tsc --noEmit
pnpm vitest run --coverage

# 全量
make check       # lint + type + test
make format      # 自动修复格式
```

### 4.3 测试要求

- 单元测试覆盖所有边界分支（空列表、网络超时、JSON 解析失败）
- 集成测试 mock GitHub API，验证完整 pipeline JSON 产出
- 不依赖真实网络（CI 环境不可靠）；本地测试可加 `integration` 标记

---

## 5. Git 规约

```
<type>(<scope>): <简短描述>

[可选正文，解释 why 而非 what]
```

**type**: `feat` / `fix` / `refactor` / `chore` / `docs` / `test` / `style`

**scope**: `py` / `ts` / `both`

示例：
```
feat(py): implement trending fetcher with rate limiting
fix(ts): handle empty categories in health check
refactor(both): align error codes between stacks
```

- 分支名：`feat/<short-desc>`、`fix/<short-desc>`
- PR 标题同 commit 规范，PR 正文附 `_health.json` 截图（如适用）

---

## 6. 编辑器 / IDE

- 项目根 `.editorconfig` 统一缩进、行尾、编码
- VS Code 推荐插件：Ruff、Biome、Python、Prettier（仅用于其他格式）
- `.vscode/settings.json` 锁定默认格式化工具

---

## 7. 跨会话指令

- 本文件是编码规约的唯一权威来源，与 `v1/specs/project-vision.md` 并列
- 新 Agent 会话开始后应先读此文件，再读项目已有代码中的现有模式
- 任何规约变更必须先更新本文件，然后统一重构代码
- AI Agent 生成的代码必须符合本文件的全部约束
