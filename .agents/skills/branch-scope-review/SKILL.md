---
name: branch-scope-review
description: Use when reviewing whether backend or frontend branches contain out-of-scope changes before commit, merge, or push, especially when docs changes are allowed but require separate user confirmation.
---

# Branch Scope Review

## 何时使用

在以下场景使用：

- 准备提交 `backend` 或 `frontend` 分支
- 准备把 `backend` / `frontend` 合到 `main`
- 准备 push，但不确定是否混入了另一端代码、废弃代码或不该带上的产物

如果当前是明确的集成分支（integration branch），可以不套这个 skill。

## 核心原则

- `backend` 分支只默认承载后端代码改动
- `frontend` 分支只默认承载前端代码改动
- `docs/**`、`README.md`、`AGENTS.md` 在两个分支里都允许改
- 但文档改动不能静默带过，必须单独列出，并向用户做一次明确确认
- 如果发现越界改动，不要直接 merge；先隔离、还原、拆分或改走集成分支

## EvoCanvas 默认边界

### backend 分支

默认视为职责内：

- `app/**`
- `tests/**`

重点警惕：

- `frontend/**`
- `traces/**`
- `tmp/**`
- `output/**`
- `workspace/**`
- 被意外带回主路径的旧废弃代码

### frontend 分支

默认视为职责内：

- `frontend/**`

重点警惕：

- `app/**`
- `tests/**`
- `traces/**`
- `tmp/**`
- `output/**`
- `workspace/**`
- 被意外带回主路径的旧废弃代码

### 文档改动

以下路径默认允许出现在两个分支：

- `docs/**`
- `README.md`
- `AGENTS.md`

但必须单独确认，不能和代码改动一起默认通过。

## 执行流程

### 1. 先看相对主线到底改了什么

优先看：

```bash
git diff --name-only main...HEAD
git diff --stat main...HEAD
```

如果当前不是 `HEAD`，就把 `HEAD` 换成待检查分支名。

## 2. 把改动分成三桶

必须显式分成：

1. 职责内改动
2. 文档改动（待确认）
3. 越界改动

输出时不要只说“整体没问题”，要把越界和文档单独列出来。

## 3. 发现文档改动时的处理

如果有文档改动：

- 单独列出文档路径
- 明确告诉用户：这些改动默认允许，但需要单独确认
- 在得到确认前，不要把“文档也算通过”当成既定事实

确认问法要直接，例如：

- “这次分支里有这些文档改动，要不要一起保留并合入？”

不要把文档确认埋在长段说明里。

## 4. 发现越界改动时的处理

如果有越界改动：

- 不要直接 merge / push
- 明确指出是哪一类越界
- 给用户收敛选项，例如：
  - 从当前分支移除
  - 单独拆到另一分支
  - 改走集成分支
  - 只 cherry-pick 需要的 commit

如果越界内容是旧产品语义或废弃资产回流，要明确标出来，不要当普通文件带过。

## 5. merge 前的最小检查

在准备 merge 到 `main` 前，至少再做一次：

```bash
git diff --name-only main...<branch>
```

然后确认：

- backend 分支里没有前端代码
- frontend 分支里没有后端代码
- 文档改动已经被单独确认
- 没有把 traces、tmp、output、workspace 之类误带进去
- 没有把旧产品语义或废弃代码重新推回主路径

## 6. 旧语义回流检查

如果这次改动涉及产品语义迁移，额外检查：

```bash
rg -n "EvoLoop|任务大厅|PRD 生成器|manual-agent" app frontend docs
```

如果命中结果出现在不该回流的位置，要单独提示，不要静默忽略。

## 输出格式

默认按下面结构汇报：

### 职责内改动

- 列路径或按目录汇总

### 文档改动（需确认）

- 列路径
- 明确请求确认

### 越界改动（需处理）

- 列路径
- 说明为什么越界
- 给出处理建议

## 禁止事项

- 不要只看 commit message 就判断可以 merge
- 不要把文档改动自动视为已确认
- 不要因为“只是几个文件”就忽略越界
- 不要把旧废弃代码、trace、产物目录混进主线
- 不要在发现越界后继续直接推进 merge
