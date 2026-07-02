# EvoCanvas Harness 文档集

> 当前整体判断：`文档集处于重构中，主骨架已从 ETCLOVG 分类法切换为实践型 harness 架构`
> 编码门槛：`已达到 L3 的子文档可指导第一批实现；未标注或仍为 L1/L2 的子文档只作为设计输入`

这组文档不是对当前后端实现的逐行解释，也不以现有代码结构作为唯一事实来源。

它们的目的只有一个：

- 定义 EvoCanvas 1.0 如何把 AI 从“会生成文本的模型”约束成“能推动产品思考状态收敛的受控系统”。

## 1. 主骨架调整

本轮重构后，`docs/harness/` 不再把 `ETCLOVG` 当成项目主骨架。

`ETCLOVG` 仍然保留，但降级为参考模型：

- 它适合做 agent harness 缺陷归因、外部论文语境对齐和分层对照。
- 它不直接决定 EvoCanvas 文档目录、对象模型、状态机或实现优先级。

EvoCanvas 当前采用更贴近工程落地的实践型 harness 公式：

```md
Harness = Instructions + Context + Memory + Runtime + Tools + Orchestration + Lifecycle + Safety + Governance + Observability + Verification + Evaluation
```

这不是为了堆概念，而是为了让每个后端能力都有明确边界：

- 指令告诉系统“应该怎么做”。
- 上下文告诉系统“当前正在处理什么”。
- 记忆告诉系统“过去沉淀了什么，哪些能被复用”。
- 运行时提供受控执行边界。
- 工具提供外部能力接入面。
- 编排决定本轮如何调度。
- 生命周期定义任务和对象如何跨阶段演化。
- 安全负责防出事。
- 治理负责定生效边界。
- 可观测性负责留痕、回放和归因。
- 验证负责判断这一次是否做对。
- 评估负责判断系统长期是否有价值。

## 2. 文档组织规范

后续各组默认采用“分组目录 + 主文档 + 子文档”结构：

- 顶层目录使用 `00-`、`01-`、`02-` 顺序编号，表达阅读顺序。
- 每个目录的主文档默认命名为 `00 English Name（中文名）.md`。
- 子文档默认命名为 `01 English Name（中文名）.md`、`02 English Name（中文名）.md`。
- 主文档负责讲关系、边界、主链和阅读入口。
- 子文档只展开主文档里已经出现、且需要单独讲清楚的问题。
- 不再把子文档链接集中堆在文末，而应放到对应正文位置。

## 3. 阅读顺序

建议按以下顺序阅读：

1. `00-overview/`：总览、边界、核心对象和运行主链。
2. `01-instructions-context/`：指令与上下文，定义模型看什么、按什么规则理解任务。
3. `02-memory-state/`：记忆与状态，定义系统如何记住、如何保持一致。
4. `03-runtime-tools/`：运行时与工具，定义受控执行和外部能力接入。
5. `04-orchestration-lifecycle/`：编排与生命周期，定义如何推进、暂停、回流和完成。
6. `05-safety-governance/`：安全与治理，定义风险拦截、权限和事实生效边界。
7. `06-observability/`：可观测性，定义 trace、回执、回放和归因。
8. `07-verification/`：验证，定义单次过程或输出是否过关。
9. `08-evaluation/`：评估，定义系统长期价值和产品效果如何判断。
10. `09-reference-models/`：参考模型，保存 ETCLOVG 等外部分类框架。

## 4. 文档清单

- `00-overview/00 Overview（总览）.md`：定义 harness 总目标、产品边界和主文档地图。
- `00-overview/01 System Boundaries（系统边界）.md`：定义 EvoCanvas 1.0 的系统边界和不做什么。
- `00-overview/02 Core Object Model（核心对象模型）.md`：定义来源、解释、待澄清、约束、决策、交接包等核心对象。
- `00-overview/03 Main Runtime Loop（运行主链）.md`：定义从输入到交接的主推进链路。

- `01-instructions-context/00 Instructions and Context（指令与上下文）.md`：说明指令和上下文的关系。
- `01-instructions-context/01 Instructions（指令）.md`：定义系统指令、产品指令、任务指令和用户指令的层级。
- `01-instructions-context/02 Context（上下文）.md`：定义当前工作面包含什么、不包含什么。
- `01-instructions-context/03 Context Assembly（上下文装配）.md`：定义上下文装配和复水规则。
- `01-instructions-context/04 AI Assistant Working Surface（AI 助手工作面）.md`：定义右侧 AI 助手的当前工作面与变化摘要角色。
- `01-instructions-context/05 Prompt Control（提示控制）.md`：定义指令如何组织成模型当前回合可执行的语言控制面。

- `02-memory-state/00 Memory and State（记忆与状态）.md`：说明记忆与状态的关系。
- `02-memory-state/01 Memory（记忆）.md`：定义原始材料、工作对象、稳定结论和冷历史。
- `02-memory-state/02 State Ledger（状态账本）.md`：定义状态账本最小记录范围。
- `02-memory-state/03 Stable State and Handoff（稳定状态与交接）.md`：定义稳定状态与结构化交接的关系。

- `03-runtime-tools/00 Runtime and Tools（运行时与工具）.md`：说明运行时与工具的关系。
- `03-runtime-tools/01 Runtime（运行时）.md`：定义受控回合、运行边界、失败恢复和状态写入边界。
- `03-runtime-tools/02 Tool Contract（工具契约）.md`：定义工具接入、来源协议和工具结果入链规则。
- `03-runtime-tools/03 Failure and Recovery（失败与恢复）.md`：定义重试、挂起、恢复和失败回执。

- `04-orchestration-lifecycle/00 Orchestration and Lifecycle（编排与生命周期）.md`：说明编排与生命周期的关系。
- `04-orchestration-lifecycle/01 Orchestration（编排）.md`：定义单轮、多模块和复杂回合的调度规则。
- `04-orchestration-lifecycle/02 Lifecycle（生命周期）.md`：定义任务和对象跨阶段演化规则。
- `04-orchestration-lifecycle/03 Stage Progression（阶段推进）.md`：定义阶段推进与停留规则。
- `04-orchestration-lifecycle/04 Gate Adjudication（门禁裁决）.md`：定义高影响动作什么时候必须挂起确认。
- `04-orchestration-lifecycle/05 Complex Turn Orchestration（复杂回合编排）.md`：定义复杂输入、冲突和多候选方向下的一轮如何拆解。
- `04-orchestration-lifecycle/06 Implementation Baseline（实现基线）.md`：汇总编排与生命周期当前最小实现基线。

- `05-safety-governance/00 Safety and Governance（安全与治理）.md`：说明安全与治理的关系。
- `05-safety-governance/01 Safety（安全）.md`：定义语义安全、风险拦截和防误导边界。
- `05-safety-governance/02 Governance（治理）.md`：定义事实生效、确认、回退和追溯边界。
- `05-safety-governance/03 Governance Baseline（治理基线）.md`：汇总状态机、确认提案队列和治理回执的最小基线。
- `05-safety-governance/04 Facts and Risk（事实与风险）.md`：定义事实可用性层级和风险分级。
- `05-safety-governance/05 Object Governance（对象治理）.md`：定义核心卡片对象的状态与治理规则。
- `05-safety-governance/06 Handoff Governance（交接物治理）.md`：定义结构化交接物的确认、过时与禁令。
- `05-safety-governance/07 Authority and Guardrails（权限与护栏）.md`：定义 AI、系统与用户之间的动作权限。

- `06-observability/00 Observability（可观测性）.md`：定义 trace、回执、来源链和诊断口径。
- `06-observability/01 Change Receipt（变化回执）.md`：定义右侧 AI 助手变化摘要的最小内容。
- `06-observability/02 Trace Model（追踪模型）.md`：定义回合、状态差异、治理、来源链和异常追踪。
- `06-observability/03 Diagnostic Views（诊断视角）.md`：定义输入、上下文、编排、治理和验证问题的诊断视角。
- `07-verification/00 Verification（验证）.md`：定义单次过程 / 输出的过关标准。
- `08-evaluation/00 Evaluation（评估）.md`：定义长期系统价值和产品效果评估。
- `08-evaluation/01 Independent Evaluation（独立评估）.md`：定义高价值结果的额外复核口径。
- `08-evaluation/02 Evaluation Metrics（评估指标）.md`：定义待澄清、冲突、约束、交接物和下游误解相关指标。
- `09-reference-models/00 Reference Models（参考模型）.md`：定义外部参考模型的使用方式。
- `09-reference-models/01 ETCLOVG Framework（ETCLOVG 模型总览）.md`：保留 ETCLOVG 原始框架说明。
- `09-reference-models/02 ETCLOVG Mapping（ETCLOVG 映射）.md`：说明 ETCLOVG 如何映射到 EvoCanvas 当前实践骨架。

## 5. 两个硬边界

### 5.1 验证和评估必须分开

- 验证（verification）回答：`这一次是否做对？`
- 评估（evaluation）回答：`这个系统长期是否真的有用？`

因此，评估不再作为验证的子章节存在。

### 5.2 编排工作流和业务工作流必须分开

- 编排工作流（orchestration workflow）属于 harness，描述 agent 如何运行。
- 业务工作流（business workflow）是 harness 服务和改造的对象，描述产品经理如何从模糊输入收敛到交接。

EvoCanvas 的 harness 不能把业务流程直接硬编码成单一生成链路，而应该用受控编排去服务产品思考收敛。

## 6. 成熟度层级与编码门槛

文档仍沿用四级成熟度：

- `L1 产品原则层`
- `L2 对象与流程定义层`
- `L3 可指导实现的治理规格层`
- `L4 可直接编码的运行时规格层`

当前规则：

- 达到 `L3` 的模块，可以作为第一批实现、接口设计和测试设计输入。
- 未达到 `L3` 的模块，只能作为方向和边界参考。
- 每次重组或改写 harness 文档，都应同步检查受影响模块的成熟度判断。

## 7. 核心立场

- EvoCanvas 不是文档生成器，也不是自由聊天框。
- EvoCanvas 的核心不是让 AI 抢先给结论，而是让 AI 在受控边界内推动状态收敛。
- Harness 的第一职责不是增强生成，而是约束生成、验证生成、追溯生成，并把生成结果转化为结构化工作状态。
