# EvoCanvas OKF Memo（OKF 判断备忘）

## 1. 文档定位

本文档用于沉淀 `OKF`（Open Knowledge Format，开放知识格式）的关键信息，并判断它与 EvoCanvas 1.0 的关系。

它不是新的产品真相源，也不替代以下文档：

1. `docs/vision/EvoCanvas1.0-PRD.md`
2. `docs/harness/02-memory-state/03 Stable State and Handoff（稳定状态与交接）.md`

如果本文档与主 PRD 存在冲突，以主 PRD 为准。

## 2. 先给结论

`OKF` 不是数据文件格式，也不是传统意义上的导出文档格式。

更准确地说，它是一种：

`面向人和 AI agent 的知识上下文交换格式`

它要解决的问题，不是“怎么存一份 CSV / Parquet 数据”，而是“怎么把关于数据、规则、口径、约束、来源和不确定性的上下文，整理成一个可以被人阅读、被 agent 逐层消费、被 Git 持续维护的知识包”。

对 EvoCanvas 的意义是：

- 它不是 1.0 首版必须内建的主路径能力。
- 但它非常适合作为 EvoCanvas 后续“结构化交接物（structured handoff）对外交换层”的参考模型。
- 它比“直接把聊天记录丢给下游 AI”更接近我们要的“可继续推进的上下文包”。

## 3. 来源与时间

这次讨论所指的 OKF，来自 Google Cloud Blog：

- 标题：`How the Open Knowledge Format can improve data sharing`
- 页面日期：`June 13, 2026`

如果外部转述写成 `2026 年 6 月 12 日`，更可能是时区、转载时间或二手转述差异；以 Google Cloud Blog 页面日期为准。

参考链接：

- [Google Cloud Blog：How the Open Knowledge Format can improve data sharing](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing)
- [GoogleCloudPlatform / knowledge-catalog / okf](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf)
- [OKF SPEC.md](https://raw.githubusercontent.com/GoogleCloudPlatform/knowledge-catalog/main/okf/SPEC.md)

## 4. OKF 到底是什么

按 Google 当前公开描述，OKF v0.1 本质上是一个目录，里面放：

1. `Markdown` 文档
2. 每个文档顶部的 `YAML frontmatter`
3. 文档之间的普通链接关系

也就是：

`目录 + Markdown + YAML 元数据 + 链接`

这种设计的核心优点不是“新”，而是“足够朴素”：

- 人可以直接读
- agent 可以直接 ingest
- Git 可以直接 diff
- 不依赖单一厂商平台

## 5. 它不是什么

为了避免误解，先把边界讲清楚。

OKF 不是：

- `CSV`、`Parquet`、`Avro` 这类数据存储格式
- `OpenAPI`、`Protobuf` 这类接口或消息 schema
- 新的企业知识库产品
- 一个自动帮你得出结论的推理框架

它更像是：

`把知识上下文组织成可交换文件包的开放约定`

## 6. 最小结构怎么理解

一个最小 OKF bundle，通常可以理解为：

```text
bundle/
├── index.md
├── log.md
├── concept-a.md
├── concept-b.md
└── concept-c.md
```

其中：

- `index.md`：入口页，告诉人和 agent 这包里有什么
- `log.md`：变更记录
- 其他 `*.md`：每个文件承载一个概念（concept）

一个 concept 文件顶部通常有 YAML frontmatter，例如：

```md
---
type: metric
title: 净营收口径
description: 定义日报里的净营收计算方式
resource: metric://daily_net_revenue
tags:
  - revenue
  - metric
timestamp: 2026-07-02T10:00:00Z
---
```

根据当前公开规范，`type` 是最关键的最小必填字段，其他字段属于推荐字段。

## 7. 它真正承载的是什么

OKF 承载的不是“原始值”，而是“理解原始值所需的上下文”。

常见内容包括：

- 表和字段的业务含义
- 指标口径
- join 路径
- API 或系统能力边界
- runbook（运行手册）
- 已知风险
- 已确认规则
- 待确认事项
- 来源与引用关系

从这个角度看，OKF 最有价值的地方在于：

`把散落在 wiki、注释、共享盘、口头经验和资深同事脑中的上下文，变成可读、可追溯、可搬运的知识包`

## 8. 它和 AGENTS.md、LLM Wiki 的关系

这也是 Google 这波最值得注意的地方。

如果只看工程实践，OKF 可以被理解为对以下模式的一次“规范化整理”：

- `AGENTS.md`
- `CLAUDE.md`
- `LLM Wiki`
- 各类“metadata as code”仓库

这些实践已经证明：

- agent 需要可读上下文
- 单靠聊天历史不够
- 单靠传统文档也不够
- 最稳定的载体往往还是文件、目录、链接与版本管理

OKF 试图做的，不是发明全新范式，而是把这类实践提升成一种更标准的交换格式。

## 9. 它和 EvoCanvas 的关系

### 9.1 一致的地方

OKF 与 EvoCanvas 1.0 在理念上高度一致：

1. 都不把“漂亮文档”当作第一目标。
2. 都强调上下文质量，而不是文本长度。
3. 都适合表达来源、约束、待确认和未决问题。
4. 都服务“继续推进”，而不是只服务“归档完成”。

尤其是 EvoCanvas 主 PRD 里强调的：

`输入编译 -> 待澄清问题 -> 约束 / 待决策 -> 结构化交接物`

和 OKF 的知识包思想有明显同向性。

### 9.2 不同的地方

但两者并不等价。

EvoCanvas 1.0 当前主路径更偏：

`上游收敛工作台`

也就是：

- 接住模糊感觉
- 暴露不确定性
- 沉淀约束
- 形成待决策
- 收束结构化交接物

而 OKF 更偏：

`下游可交换知识包`

也就是：

- 把已整理出的上下文装进文件目录
- 让人和 agent 能继续消费
- 用开放格式对外传递

一句话说：

`EvoCanvas 负责把东西想清楚，OKF 更像负责把想清楚的上下文装箱。`

## 10. 它和结构化交接物的关系

当前更准确的判断不是“EvoCanvas 要不要直接变成 OKF”，而是：

`OKF 可以作为结构化交接物对外表示层的参考模型。`

因为根据现有 PRD 和 harness 文档，EvoCanvas 的结构化交接物至少要保留：

1. 当前目标
2. 输入背景
3. 已确认约束
4. 已完成决策
5. 仍未解决的问题
6. 待确认决策
7. 推荐后续动作
8. 关键来源引用

这和 OKF 的知识上下文包天然兼容。

可以这样理解两层关系：

- `结构化交接物`：EvoCanvas 内部业务语义层
- `OKF bundle`：对外交换与文件组织层

前者回答“我们交给下一位人或下一轮 AI 的最小上下文是什么”，后者回答“这份上下文如何以开放目录格式被保存、链接和传递”。

## 11. 一个对 EvoCanvas 更实用的映射

如果以后要把 EvoCanvas 输出映射到 OKF，可以先用下面这套最小对应关系：

### 11.1 目录层

```text
handoff-bundle/
├── index.md
├── log.md
├── target.md
├── constraints.md
├── decisions.md
├── open-questions.md
├── next-actions.md
└── sources/
    ├── source-001.md
    └── source-002.md
```

### 11.2 EvoCanvas 对象到 OKF 文件的映射

- `当前目标` -> `target.md`
- `约束卡` -> `constraints.md`
- `待决策 / 已决策卡` -> `decisions.md`
- `待澄清问题` -> `open-questions.md`
- `推荐后续动作` -> `next-actions.md`
- `来源片段 / 来源说明` -> `sources/*.md`

### 11.3 一个关键原则

不应把整段聊天记录原封不动导出为 OKF。

因为 EvoCanvas 的主线不是“保存原话”，而是“先收敛，再交接”。

所以如果以后支持 OKF 导出，输出主体仍应来自：

- 已治理过的对象
- 已分层的状态
- 已保留的未决与风险

而不是原始聊天转储。

## 12. 当前阶段不该误判的地方

基于 EvoCanvas 1.0 当前范围，以下几件事不应误判：

1. 不应因为 OKF 很新，就把产品主线改成“做一个知识库平台”。
2. 不应把 OKF 误当成首版必须交付的用户可见主功能。
3. 不应为了支持 OKF，而跳过“先暴露不确定性、再沉淀约束、再形成待决策”的主链。
4. 不应把 OKF 导出等同于“生成完整 PRD”。

当前最稳的判断是：

`OKF 是 EvoCanvas 后续对外交接层的强参考，不是 1.0 当前主战场。`

## 13. 当前阶段值得保留的机会

虽然它不是 1.0 主路径，但值得提前记住三类机会：

1. `面向下游 AI 的交付标准化`
   如果未来要把结构化交接物交给 Codex、Claude Code、Antigravity 等下游工具，OKF 这种文件化知识包会比自由长文更稳。

2. `上下文版本管理`
   结构化交接物一旦要跨轮迭代、跨角色流转，基于 Markdown 与 Git 的表示层会天然更可追踪。

3. `知识资产沉淀`
   当同类问题、规则、口径反复出现时，OKF 形态比聊天记录更适合作为可复用资产。

## 14. 现阶段内部判断

如果只保留一句判断，建议记住：

`OKF 不是 EvoCanvas 要去替代的对象，而是 EvoCanvas 未来可以借用的交接格式思想。`

再展开一层就是：

- EvoCanvas 先把“模糊输入如何被塑形成可交接判断”做到成立
- OKF 再作为这份判断对外传递、被 agent 继续消费时的开放包层参考

这条顺序不能倒。

