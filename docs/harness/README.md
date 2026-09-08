# EvoCanvas Harness 文档集

> 当前成熟度：`十二项方法的 47 份现行规范均已达到 L3 可指导实现的治理规格层`
> 当前同步状态：`Harness、主 PRD、模块文档、现行技术规格与机器 Schema 已对齐；现行规格目录不再保留历史快照`
> 当前实现状态：`Pi 长期 Session、统一提交器和投影链仍有迁移缺口`
> 产品真相源：[`docs/vision/EvoCanvas1.0-PRD.md`](../vision/EvoCanvas1.0-PRD.md)

## 1. 目的

Harness 的唯一最高目标是：**降低需求从模糊输入、对话塑形、结构固定到下游交接之间的失真。**

L3 表示实现者可以依据这些文档设计接口、状态、门禁和测试，而不需要自行发明产品规则；它不表示当前代码已经实现，也不表示真实 Pi 集成已经验证。

## 2. 统一架构

```text
用户
  <-> 一个 Workspace 的 Primary Pi Session
        ├─ Pi System Instructions / Skills
        ├─ 原始 User / Assistant / Tool Entry
        ├─ transformContext 读取最新稳定 Revision
        └─ 受治理的 EvoCanvas Tools
              ├─ 读取对象、历史与来源
              └─ workspace.commit
                    -> Workspace Artifact（结构化工作包）的不可变 Revision
                          ├─ Canvas Renderer 显影
                          └─ 已确认交接物派生
```

共同地基：

1. Pi Agent Core 是唯一 Agent 运行核心。
2. 空 Workspace 可以没有 Session；第一条真实消息后，一个 Workspace 对应一个长期 Primary Pi Session 和一个逻辑 Workspace Artifact（结构化工作包）。
3. Session 保存过程，完整不可变 Revision 保存稳定状态。
4. EvoCanvas 只给 Pi 安装产品 Instructions、Skills、工具、治理 Hooks 和 Canvas Renderer。
5. Pi 与用户直接编辑共用同一语义提交能力。
6. 候选留在 Session；来源事实完整性收录和已确认语义才可进入工作包。
7. Canvas 只显影稳定 Revision；结构化交接物只派生自已确认 Revision。
8. 不建立 Pi 外部 Agent Kernel、Supervisor、阶段路由、独立收敛运行、平行历史、上下文清单或状态账本。
9. User Submission、Session Entry、稳定操作和工具调用分别使用 `submission_id / entry_id / operation_id / invocation_id`。
10. 工具只声明 `replay: safe | never`；结果 `unknown` 不构成自动重放许可。

## 3. 十二项方法与实现映射

| Harness 方法 | L3 控制目标 | 目标实现归属 | 当前实现状态 |
| --- | --- | --- | --- |
| Instructions | 永久原则、按需方法、机器门禁和用户原话保真 | EvoCanvas 指令/Skills 装入 Pi | 部分接入 |
| Context | Session、稳定工作锚点、按需复水和降级 | Pi Session + `transformContext` | 部分接入 |
| Memory | 过程与稳定状态分离、Revision 和来源保留 | Pi Session + 结构化工作包 | 代码待迁移 |
| Runtime | 唯一 Agent Loop、恢复、取消、压缩和技术 Trace | Pi Agent Core | 部分接入 |
| Tools | 读取、稳定写入和外部副作用合同 | Pi Tool Loop + EvoCanvas 工具 | 代码待迁移 |
| Orchestration | 同一 Pi 如何选择并推进下一步 | Pi 原生 Tool Loop；不是独立组件 | 代码待迁移 |
| Lifecycle | Session、Revision、对象、交接和投影的终态 | Pi 技术状态 + 工作包稳定状态 | 代码待迁移 |
| Safety | 防误导、越权、泄露和未知副作用 | Pi 保护 + 工具护栏 | 代码待迁移 |
| Governance | 信息与动作何时生效、谁裁决 | 用户 + 确定性提交器 | 代码待迁移 |
| Observability | 从 Entry 到 Revision 和投影的追溯 | Pi Trace + Revision 审计 + 投影检查点 | 代码待迁移 |
| Verification | 单次结构、来源和 Policy 是否过关 | 确定性验证器 | 代码待迁移 |
| Evaluation | 长期是否降低需求失真 | EvoCanvas 离线评估控制面 | 评估集待建设 |

Pi 不是第十三项 Harness 方法，而是多项方法的统一实现底座。Orchestration 作为方法保留，是为了冻结推进顺序与不可绕过的不变量，不对应新服务。

## 4. 权威记录与确认边界

| 事实 | 权威记录 |
| --- | --- |
| 用户、Pi 和工具实际发生过什么 | Pi Session / Technical Trace |
| 当前稳定业务状态 | `current_revision_id` 指向的结构化工作包 Revision |
| 下游默认可用交接 | `latest_confirmed_handoff_revision_id` |
| 外部副作用是否成功 | 外部工具回执与幂等查询 |
| Canvas 显示到哪个版本 | Projection Checkpoint |

Pi 可提出和分析；用户确认产品含义、范围、交接和风险；工具执行身份、版本、Schema、状态、确认和幂等门禁。工作包确认、交接确认和外部行动授权相互独立。

## 5. L3 统一门槛

每篇规范性文档必须明确或引用同组权威定义：

1. 控制目标；
2. 实现归属；
3. 权威输入输出；
4. 权限与确认边界；
5. 状态推进、回退和过时；
6. 失败与恢复；
7. 验收场景。

成熟度与实现状态分开。代码仍使用旧兼容路径时，应标记迁移缺口，不能让旧实现反向定义目标 Harness。

## 6. 阅读顺序

### 6.1 总览与公共模型

- [`00-overview/00 Overview（总览）.md`](<00-overview/00 Overview（总览）.md>)
- [`00-overview/01 System Boundaries（系统边界）.md`](<00-overview/01 System Boundaries（系统边界）.md>)
- [`00-overview/02 Core Object Model（核心对象模型）.md`](<00-overview/02 Core Object Model（核心对象模型）.md>)
- [`00-overview/03 Main Runtime Loop（运行主链）.md`](<00-overview/03 Main Runtime Loop（运行主链）.md>)
- [`00-overview/04 Maturity Levels（成熟度层级）.md`](<00-overview/04 Maturity Levels（成熟度层级）.md>)
- [`00-overview/05 Convergence Readiness（收敛就绪度）.md`](<00-overview/05 Convergence Readiness（收敛就绪度）.md>)

### 6.2 Instructions 与 Context

- [`01-instructions-context/00 Instructions and Context（指令与上下文）.md`](<01-instructions-context/00 Instructions and Context（指令与上下文）.md>)
- [`01-instructions-context/01 Instructions（指令）.md`](<01-instructions-context/01 Instructions（指令）.md>)
- [`01-instructions-context/02 Context（上下文）.md`](<01-instructions-context/02 Context（上下文）.md>)
- [`01-instructions-context/03 Context Assembly（上下文装配）.md`](<01-instructions-context/03 Context Assembly（上下文装配）.md>)
- [`01-instructions-context/04 AI Assistant Working Surface（AI 助手工作面）.md`](<01-instructions-context/04 AI Assistant Working Surface（AI 助手工作面）.md>)
- [`01-instructions-context/05 Prompt Control（提示控制）.md`](<01-instructions-context/05 Prompt Control（提示控制）.md>)
- [`01-instructions-context/06 Context Budget and Compaction（上下文预算与压缩）.md`](<01-instructions-context/06 Context Budget and Compaction（上下文预算与压缩）.md>)

### 6.3 Memory 与 State

- [`02-memory-state/00 Memory and State（记忆与状态）.md`](<02-memory-state/00 Memory and State（记忆与状态）.md>)
- [`02-memory-state/01 Memory（记忆）.md`](<02-memory-state/01 Memory（记忆）.md>)
- [`02-memory-state/02 State Model（状态模型）.md`](<02-memory-state/02 State Model（状态模型）.md>)
- [`02-memory-state/03 Stable State and Handoff（稳定状态与交接）.md`](<02-memory-state/03 Stable State and Handoff（稳定状态与交接）.md>)
- [`02-memory-state/04 Convergence Decisions（收敛决策基线）.md`](<02-memory-state/04 Convergence Decisions（收敛决策）.md>)

### 6.4 Runtime 与 Tools

- [`03-runtime-tools/00 Runtime and Tools（运行时与工具）.md`](<03-runtime-tools/00 Runtime and Tools（运行时与工具）.md>)
- [`03-runtime-tools/01 Runtime（运行时）.md`](<03-runtime-tools/01 Runtime（运行时）.md>)
- [`03-runtime-tools/02 Tool Contract（工具契约）.md`](<03-runtime-tools/02 Tool Contract（工具契约）.md>)
- [`03-runtime-tools/03 Failure and Recovery（失败与恢复）.md`](<03-runtime-tools/03 Failure and Recovery（失败与恢复）.md>)

### 6.5 Orchestration 与 Lifecycle

- [`04-orchestration-lifecycle/00 Orchestration and Lifecycle（编排与生命周期）.md`](<04-orchestration-lifecycle/00 Orchestration and Lifecycle（编排与生命周期）.md>)
- [`04-orchestration-lifecycle/01 Orchestration（编排）.md`](<04-orchestration-lifecycle/01 Orchestration（编排）.md>)
- [`04-orchestration-lifecycle/02 Lifecycle（生命周期）.md`](<04-orchestration-lifecycle/02 Lifecycle（生命周期）.md>)
- [`04-orchestration-lifecycle/03 Convergence Operations（收敛操作）.md`](<04-orchestration-lifecycle/03 Convergence Operations（收敛操作）.md>)
- [`04-orchestration-lifecycle/04 Gate Adjudication（门禁裁决）.md`](<04-orchestration-lifecycle/04 Gate Adjudication（门禁裁决）.md>)
- [`04-orchestration-lifecycle/05 Implementation Baseline（实现基线）.md`](<04-orchestration-lifecycle/05 Implementation Baseline（实现基线）.md>)

### 6.6 Safety 与 Governance

- [`05-safety-governance/00 Safety and Governance（安全与治理）.md`](<05-safety-governance/00 Safety and Governance（安全与治理）.md>)
- [`05-safety-governance/01 Safety（安全）.md`](<05-safety-governance/01 Safety（安全）.md>)
- [`05-safety-governance/02 Governance（治理）.md`](<05-safety-governance/02 Governance（治理）.md>)
- [`05-safety-governance/03 Governance Baseline（治理基线）.md`](<05-safety-governance/03 Governance Baseline（治理基线）.md>)
- [`05-safety-governance/04 Facts and Risk（事实与风险）.md`](<05-safety-governance/04 Facts and Risk（事实与风险）.md>)
- [`05-safety-governance/05 Object Governance（对象治理）.md`](<05-safety-governance/05 Object Governance（对象治理）.md>)
- [`05-safety-governance/06 Handoff Governance（交接物治理）.md`](<05-safety-governance/06 Handoff Governance（交接物治理）.md>)
- [`05-safety-governance/07 Authority and Guardrails（权限与护栏）.md`](<05-safety-governance/07 Authority and Guardrails（权限与护栏）.md>)

### 6.7 Observability、Verification 与 Evaluation

- [`06-observability/00 Observability（可观测性）.md`](<06-observability/00 Observability（可观测性）.md>)
- [`06-observability/01 Projection Signals（显影提示）.md`](<06-observability/01 Projection Signals（显影提示）.md>)
- [`06-observability/02 Trace Model（追踪模型）.md`](<06-observability/02 Trace Model（追踪模型）.md>)
- [`06-observability/03 Diagnostic Views（诊断视角）.md`](<06-observability/03 Diagnostic Views（诊断视角）.md>)
- [`07-verification/00 Verification（验证）.md`](<07-verification/00 Verification（验证）.md>)
- [`07-verification/01 Structure Verification（结构验证）.md`](<07-verification/01 Structure Verification（结构验证）.md>)
- [`07-verification/02 Source Verification（来源验证）.md`](<07-verification/02 Source Verification（来源验证）.md>)
- [`07-verification/03 Policy Verification（策略验证）.md`](<07-verification/03 Policy Verification（策略验证）.md>)
- [`08-evaluation/00 Evaluation（评估）.md`](<08-evaluation/00 Evaluation（评估）.md>)
- [`08-evaluation/01 Independent Evaluation（独立评估）.md`](<08-evaluation/01 Independent Evaluation（独立评估）.md>)
- [`08-evaluation/02 Evaluation Metrics（评估指标）.md`](<08-evaluation/02 Evaluation Metrics（评估指标）.md>)

`09-reference-models/` 保留 ETCLOVG 等历史参考，不属于当前十二项方法的规范性成熟度范围，不能覆盖上述 L3 合同。

## 7. 当前实现差距

主 PRD、模块文档、现行技术规格和机器 Schema 已同步到本 Harness 合同；旧技术快照已从现行规格目录移除。现有代码仍包含单次请求、旧运行类型、旧状态和跨进程兼容字段。完成代码迁移至少需要：

1. 统一升级 Pi `0.85.1` 依赖族，接入官方 SQLite Backend、一个 Session 一个文件和宿主独占写锁；
2. 建立首条真实消息触发的 Workspace–Primary Pi Session Binding 与恢复；
3. 接入 Pi Skills、`transformContext` 和长期 Session；
4. 统一 Pi 与用户直接编辑的 `workspace.commit`；
5. 落地身份分层、工具 replay 策略和 close/archive/replace/delete 生命周期；
6. 移除目标路径中的独立判断、收敛调度和自由整包写入；
7. 接入确认、依赖传播、交接双指针和投影 Outbox；
8. 建立 Entry–Invocation–Operation–Commit–Revision–Projection 追溯；
9. 按 Workspace 停写、导入、哈希校验和原子切换迁移旧数据，不长期双写；
10. 用端到端测试证明未确认不显影、并发不丢失、失败可恢复和下游只读有效交接。

这些是实现状态，不影响本 Harness 目标合同当前已达到 L3 的判断。
