# Architecture Traceability（架构可追溯矩阵）

## 1. 文档目的

本文核对 [System Architecture（系统总架构）](<./03 System Architecture（系统总架构）.md>) 中的目标节点和关键依赖，判断它们当前由什么证据支撑，以及是否有资格反向推动 Harness 文档调整。

本文不修改 Harness 规则，也不提升任何文档的成熟度。它只做四件事：

1. 找到目标架构节点与现有 PRD、Harness、技术规格之间的对应关系。
2. 区分既有 L3 规格、L2 定义、产品或技术边界、目标假设和真实冲突。
3. 防止系统架构图反向创造未经确认的 Harness 规则。
4. 给后续最小定向调整提供进入条件和停止条件。

证据优先级仍然是：

```text
主 PRD
-> Harness 中已确认且达到相应成熟度的规则
-> 技术规格与目标架构
-> 当前代码承接
```

系统架构可以聚合和解释已有规则，但不能仅凭一个节点或箭头把 L1 / L2 判断升级成 L3。

## 2. 状态说明

| 状态 | 含义 | 后续动作 |
| --- | --- | --- |
| `L3` | 已有 Harness L3 规格直接支撑 | 只允许补链接、术语映射或执行载体说明 |
| `L2` | 已有对象或流程定义，但未达到稳定实现规格 | 保持成熟度，不直接生成接口、状态机或发布流程 |
| `BOUNDARY` | 属于 PRD、界面或技术接入边界，不应由 Harness 独占定义 | 在 Harness 总览中说明关系，不新增平行规则 |
| `TARGET` | 目标架构提出的新组织方式或尚未确认的能力 | 先做产品或架构决策，再决定是否进入 Harness |
| `CONFLICT` | 与现有真相源、权限或成熟度存在冲突 | 停止写回，先修改架构解释或完成单独决策 |

组合节点按“完成该节点职责所必需的最低成熟度”判定，而不是因为其中一条依赖已有 L3 合同，就把整个节点标成 L3。表格判断栏可以同时说明其已具备的 L3 底座；但只要核心语义、输入选择、产品行为或投影合同仍为 L2，该组合节点整体仍按 L2 对待。

## 3. 架构节点可追溯矩阵

### 3.1 User Interfaces（用户界面）

| 节点 | 状态 | 当前权威依据 | 判断 |
| --- | --- | --- | --- |
| Web Workspace | `BOUNDARY` | [EvoCanvas 1.0 PRD](../vision/EvoCanvas1.0-PRD.md)、[System Boundaries](<../harness/00-overview/01 System Boundaries（系统边界）.md>) | 是 1.0 主工作面；Harness 只约束其确认权、投影权和事实写权限 |
| Application API | `BOUNDARY` | [System Boundaries](<../harness/00-overview/01 System Boundaries（系统边界）.md>)、[Authority and Guardrails](<../harness/05-safety-governance/07 Authority and Guardrails（权限与护栏）.md>) | API 是协议和入口，不应持有领域裁决权；具体接口合同必须重新核对当前代码，不能引用历史 Frontend Contract 直接实现 |
| CLI / MCP | `TARGET` + `BOUNDARY` | [System Boundaries](<../harness/00-overview/01 System Boundaries（系统边界）.md>)、[Tool Contract](<../harness/03-runtime-tools/02 Tool Contract（工具契约）.md>) | “可复用但非 1.0 主路径”符合当前产品方向，但尚不需要扩成独立 Harness 运行规范 |

### 3.2 EvoCanvas Agent Core（核心运行层）

| 节点 | 状态 | 当前权威依据 | 判断 |
| --- | --- | --- | --- |
| Source Intake | `L2` + `BOUNDARY` | [Context](<../harness/01-instructions-context/02 Context（上下文）.md>)、[Tool Contract](<../harness/03-runtime-tools/02 Tool Contract（工具契约）.md>) | 来源保存与只读解析已有 L3 工具合同，但接入范围、输入工作面和“感觉接入”整体仍分别受 L2 Context 与 PRD 约束，不能把整个接入节点视为 L3 |
| Conversation Runtime | `L2` | [AI Assistant Working Surface](<../harness/01-instructions-context/04 AI Assistant Working Surface（AI 助手工作面）.md>)、[Runtime](<../harness/03-runtime-tools/01 Runtime（运行时）.md>) | Chat 的运行记录、权限和后置调度已有 L3 底座；理解、追问、建议和确认承接方式仍是 L2 产品行为定义 |
| Context Assembly | `L2` | [Context Assembly](<../harness/01-instructions-context/03 Context Assembly（上下文装配）.md>)、[Runtime](<../harness/03-runtime-tools/01 Runtime（运行时）.md>) | 五个逻辑输入面、预算、复水和 Manifest 已定义较细，且 Adapter 有 L3 约束；但装配主文档明确仍为 L2，不得直接作为完整实现合同 |
| Convergence Runtime | `L3` | [Convergence Operations](<../harness/04-orchestration-lifecycle/03 Convergence Operations（收敛操作）.md>) | 负责最小结构化提案，不拥有事实生效权 |
| Governed State Commit | `L3` | [Runtime and Tools](<../harness/03-runtime-tools/00 Runtime and Tools（运行时与工具）.md>)、[Implementation Baseline](<../harness/04-orchestration-lifecycle/05 Implementation Baseline（实现基线）.md>) | 统一提交器、版本检查、幂等和原子提交已有规则；必须解释为系统能力而非模型权限 |

### 3.3 Domain & Harness Rules（领域与 Harness 规则）

| 节点 | 状态 | 当前权威依据 | 判断 |
| --- | --- | --- | --- |
| Object Rules | `L2` | [Core Object Model](<../harness/00-overview/02 Core Object Model（核心对象模型）.md>)、[Object Governance](<../harness/05-safety-governance/05 Object Governance（对象治理）.md>) | 对象治理与状态迁移已有 L3 规则，但核心对象、关系和产品语义仍由 L2 对象模型定义；组合节点不能整体升为 L3 |
| Convergence Rules | `L2`，名称是聚合视图 | [AI Assistant Working Surface](<../harness/01-instructions-context/04 AI Assistant Working Surface（AI 助手工作面）.md>)、[Orchestration and Lifecycle](<../harness/04-orchestration-lifecycle/00 Orchestration and Lifecycle（编排与生命周期）.md>)、[Convergence Operations](<../harness/04-orchestration-lifecycle/03 Convergence Operations（收敛操作）.md>) | 运行编排、生命周期和结构化收敛操作已有 L3 子合同；但该聚合节点还约束 L2 的对话塑形、追问和停留表达，因此整体按最低必要成熟度保持 L2 |
| Governance Rules | `L3` | [Governance](<../harness/05-safety-governance/02 Governance（治理）.md>)、[Gate Adjudication](<../harness/04-orchestration-lifecycle/04 Gate Adjudication（门禁裁决）.md>) | 确认、风险、信息地位和生效边界已有规则 |
| Verification & Handoff Rules | `L3` | [Verification](<../harness/07-verification/00 Verification（验证）.md>)、[Handoff Governance](<../harness/05-safety-governance/06 Handoff Governance（交接物治理）.md>) | 单次可信条件和交接边界已有规则；验证不拥有最终放行权 |

### 3.4 State & Projection（状态与投影）

| 节点 | 状态 | 当前权威依据 | 判断 |
| --- | --- | --- | --- |
| Message & Source Store | `L3` | [Memory and State](<../harness/02-memory-state/00 Memory and State（记忆与状态）.md>)、[Tool Contract](<../harness/03-runtime-tools/02 Tool Contract（工具契约）.md>) | 原始 `user / assistant / tool`、来源和确认原文是独立权威记录 |
| Structured State & Versions | `L3` | [Memory](<../harness/02-memory-state/01 Memory（记忆）.md>)、[State Ledger](<../harness/02-memory-state/02 State Ledger（状态账本）.md>) | 结构化包、不可变版本、状态账本和指针已有稳定边界 |
| Workspace Projections | `L2` | [Memory and State](<../harness/02-memory-state/00 Memory and State（记忆与状态）.md>)、[Projection Signals](<../harness/06-observability/01 Projection Signals（显影提示）.md>) | “投影不是事实源、应可重建”的状态边界已有 L3 支撑；Canvas、Cards、Active Todos、Timeline、Handoff 和 Toast 的完整显影合同仍是 L2 |

### 3.5 Tools & Providers（工具与能力提供方）

| 节点 | 状态 | 当前权威依据 | 判断 |
| --- | --- | --- | --- |
| Model Provider | `L3` | [Runtime](<../harness/03-runtime-tools/01 Runtime（运行时）.md>)、[Prompt Control](<../harness/01-instructions-context/05 Prompt Control（提示控制）.md>) | Provider Adapter 的协议映射、能力登记和一致性测试已有 L3 合同；它消费 Context Assembly 提供的输入，不获得业务事实权，也不代表 L2 装配规则已整体升为 L3 |
| Source Resolver | `L3` | [Tool Contract §8.1](<../harness/03-runtime-tools/02 Tool Contract（工具契约）.md>)、[Source Verification](<../harness/07-verification/02 Source Verification（来源验证）.md>) | 是只读来源解析能力，结果先进入原始工具记录，不自动形成证据或结论 |
| Internal Tools | `L3` | [Tool Contract](<../harness/03-runtime-tools/02 Tool Contract（工具契约）.md>) | 读取、转换、分析和验证工具无稳定状态写权限；外部副作用另走门禁 |

### 3.6 Evaluation Control Plane（离线评估控制面）

| 节点 | 状态 | 当前权威依据 | 判断 |
| --- | --- | --- | --- |
| Evaluation & Failure Corpus | `L2` + `TARGET` | [Evaluation](<../harness/08-evaluation/00 Evaluation（评估）.md>)、[Evaluation Metrics](<../harness/08-evaluation/02 Evaluation Metrics（评估指标）.md>) | 已定义评估对象、证据和指标，但未定义语料身份、采样、脱敏、版本和保留规则 |
| Human Review | `L2` | [Independent Evaluation](<../harness/08-evaluation/01 Independent Evaluation（独立评估）.md>) | 已定义独立复核用途和输出，但没有正式发布审批职责、角色和审计合同 |
| Versioned Policy / Prompt Release | `TARGET` | [Prompt Control](<../harness/01-instructions-context/05 Prompt Control（提示控制）.md>)、[Evaluation](<../harness/08-evaluation/00 Evaluation（评估）.md>) | 版本字段已有局部基础，但没有发布工作流；目标图只允许其向 Context Assembly 提供已批准运行制品，不连接或修改 Convergence / Governance Rules |

## 4. 关键依赖可追溯矩阵

### 4.1 接入、对话与来源

| 依赖 | 状态 | 当前依据与结论 |
| --- | --- | --- |
| Web Workspace -> Application API | `BOUNDARY` | 属于产品与技术接口，不需要成为 Harness 状态机 |
| CLI / MCP -> Application API | `TARGET` + `BOUNDARY` | 可以复用入口，但必须服从与 Web 相同的事实写权限；非 1.0 主路径 |
| Application API -> Source Intake | `BOUNDARY` | API 只路由输入，不判定来源是否可信或结论是否成立 |
| Application API -> Conversation Runtime | `BOUNDARY` | API 只启动或续接 Chat，不拥有对话判断和确认裁决权 |
| Source Intake -> Message & Source Store | `L3` | 原始材料先保存并获得稳定引用，再参与上下文和收敛 |
| Conversation Runtime -> Message & Source Store | `L3` | 每条原始消息独立保存，不被结构化包替代 |

### 4.2 上下文与模型

| 依赖 | 状态 | 当前依据与结论 |
| --- | --- | --- |
| Conversation Runtime -> Context Assembly | `L2` | 统一装配边界已定义，但 Context Assembly 主合同仍为 L2；不得仅凭 Runtime 的 L3 底座直接固化完整输入选择逻辑 |
| Convergence Runtime -> Context Assembly | `L2` | 收敛应复用相同 Structured Package Input 和策略版本，但上下文选择、预算与复水主合同仍为 L2 |
| Message & Source Store -> Context Assembly | `L2` | 原始记录本身是 L3 权威记录；它们按何种范围、预算与复水规则进入模型上下文仍由 L2 装配规格定义 |
| Structured State & Versions -> Context Assembly | `L2` | 包版本和状态版本是 L3；本轮选择何种结构化输入快照并装配给模型仍是 L2 |
| Context Assembly -> Model Provider | `L2` | Provider Adapter 的协议映射与禁止静默裁剪已达 L3，但其输入由仍为 L2 的 Context Assembly 合同决定，端到端依赖不能整体标 L3 |

### 4.3 收敛、提交与投影

| 依赖 | 状态 | 当前依据与结论 |
| --- | --- | --- |
| Conversation Runtime -> Convergence Runtime | `L3` | Chat 完成后由后置判断决定是否启动收敛；“形成可沉淀增量”不是每轮必触发 |
| Convergence Runtime -> Governed State Commit | `L3` | 收敛只提交结构化操作提案，必须先经过验证与治理 |
| Governed State Commit -> Structured State & Versions | `L3` | 统一提交器执行版本检查、幂等和原子写入，是唯一稳定状态写入口 |
| Structured State & Versions -> Workspace Projections | `L2` | 投影只消费已提交状态、不得反向裁决事实的边界已有 L3 支撑；完整投影生成与显影合同仍为 L2 |
| Workspace Projections -> Application API | `BOUNDARY` + `L2` | 投影与事实分离的底线已有 L3 支撑，但投影字段和前台表达仍是 L2 / 技术契约，API 不应把它们提升为新的事实层 |

### 4.4 规则约束

| 依赖 | 状态 | 当前依据与结论 |
| --- | --- | --- |
| Object Rules -> Convergence Runtime | `L2` | L3 收敛操作已约束提案形式，但完整对象、关系和类型语义仍依赖 L2 Core Object Model |
| Object Rules -> Governed State Commit | `L2` | L3 对象治理与策略验证可以拒绝已定义的非法迁移；对象语义本身仍为 L2，不能据此宣称整个对象规则合同已可直接编码 |
| Convergence Rules -> Conversation Runtime | `L2`，聚合映射 | 后置调度与治理边界已有 L3 规则；Chat 的追问、停留和确认表达仍涉及 L2 Instructions、Working Surface 与 Prompt Control，不应收缩成单一 Prompt |
| Convergence Rules -> Convergence Runtime | `L2`，聚合映射 | 结构化收敛、回流和停止的 L3 子合同可以指导对应实现；但发起节点仍聚合 L2 对话塑形语义，端到端依赖不能整体标 L3 |
| Governance Rules -> Governed State Commit | `L3` | 治理决定信息地位能否生效，提交器执行已裁决结果 |
| Verification & Handoff Rules -> Governed State Commit | `L3` | 验证提供可信判断，治理仍拥有最终放行权 |
| Verification & Handoff Rules -> Workspace Projections | `L2` | 验证与交接状态本身已有 L3 合同；这些状态如何完整投影和提示仍为 L2，不得由界面自行推断事实 |

### 4.5 工具与来源解析

| 依赖 | 状态 | 当前依据与结论 |
| --- | --- | --- |
| Source Intake -> Source Resolver | `L3` | 只按来源引用和位置读取原文，不接受自由业务语义制造新来源 |
| Source Resolver -> Message & Source Store | `L3` | 结果先保存为原始 `tool` 消息或不可变结果记录 |
| Conversation Runtime -> Internal Tools | `L3` | Chat 只使用读取、检索、验证和来源定位等允许能力，不调用结构化状态写入 |
| Convergence Runtime -> Internal Tools | `L3` | 可调用允许的确定性工具，但结果仍须进入来源、验证和治理链 |

### 4.6 离线评估与发布

| 依赖 | 状态 | 当前依据与结论 |
| --- | --- | --- |
| Structured State & Versions -> Evaluation & Failure Corpus | `L2` + `TARGET` | 真实样本应来自运行过程，但采样、脱敏、授权、版本和保留策略尚未定义 |
| Evaluation & Failure Corpus -> Human Review | `L2` | 现有独立评估可提供复核方法，但尚未定义正式评审队列和发布责任 |
| Human Review -> Versioned Policy / Prompt Release | `TARGET` | 尚无发布对象、审批条件、版本契约、回退机制和责任人规格 |
| Versioned Policy / Prompt Release -> Context Assembly | `TARGET` | 已有 `assembly_policy_version` 等版本字段，但没有从评估结论到运行版本的发布链 |

目标架构已明确不包含 `Versioned Policy / Prompt Release -> Convergence Rules / Governance Rules` 两条依赖。若未来重新引入，它们应直接判定为 `CONFLICT`：评估控制面只能发布经过正常 PRD / Harness / 代码评审批准的运行制品，不能成为规则真相源。

## 5. 冲突裁决

### 5.1 Evaluation Control Plane 不自动获得 L3 地位

目标架构可以保留 Evaluation Control Plane，表示系统必须有离线评估边界。但在现有 Harness 中：

- Evaluation 仍为 L2。
- Failure Corpus 的数据合同尚未定义。
- Human Review 尚未形成正式审批职责。
- Policy / Prompt Release 尚无稳定发布与回退规格。

因此，现阶段不得因为主图存在该子系统，就新增 L3 发布接口、运行时状态机或动态策略注册中心。

### 5.2 Policy / Prompt Release 的权限边界

当前允许的解释是：

```text
离线评估形成候选改进
-> 人工审查
-> 修改对应 PRD / Harness / Prompt / 代码或配置
-> 走正常评审与发布
-> 线上运行消费已批准、可回退的版本
```

当前禁止的解释是：

```text
离线评估结果
-> 自动改变 Convergence Rules 或 Governance Rules
-> 直接影响线上事实生效
```

### 5.3 Agent Core 不等于模型权限边界

`Governed State Commit` 放在 Agent Core 中只表示它属于核心运行系统，不表示模型、AgentRuntime 或 Conversation Runtime 拥有稳定状态写权限。

必须保持：

```text
模型输出回复或结构化提案
-> 确定性结构 / 来源 / 策略验证
-> 治理裁决与确认范围检查
-> 版本与幂等检查
-> 系统统一提交
```

## 6. 对 Harness 的最小调整候选

本节记录最小调整候选及其当前执行状态。已执行项仍只属于架构映射、成熟度标注和权限边界澄清，不代表相关 L2 模块已经升为 L3。

| 候选调整 | 当前结论 | 进入条件 |
| --- | --- | --- |
| Harness README 增加目标架构链接和六子系统映射表 | 已执行 | 映射未替换现有十二项 Harness 公式，并明确组合节点按最低必要成熟度判断 |
| Overview 增加“系统架构视图 vs Harness 控制规格视图”说明 | 已执行 | 只链接唯一主图和本矩阵，未复制 Mermaid |
| Main Runtime Loop 对齐 Source Intake / Conversation / Context / Convergence / Commit 名称 | 已执行 | 保留两类关联回合和四类运行记录，未新增阶段状态机或提交入口 |
| System Boundaries 说明 Web 与 CLI / MCP 的入口边界 | 已执行 | CLI / MCP 保持非 1.0 产品主路径，并与 Web 共用同一治理和提交边界 |
| Prompt Control 说明版本引用不等于发布工作流 | 已执行 | 未定义新的发布对象、审批、灰度或回退机制 |
| Evaluation 与 Independent Evaluation 说明离线评估和人工复核的权限 | 已执行 | 保持 L2；未把 Human Review 变成已定义发布角色，也未形成线上自修改闭环 |
| Runtime、Memory、Tools、Governance、Verification 文档重组目录 | 不执行 | 当前无语义冲突，重组只会制造迁移成本 |
| 新增 Policy and Prompt Release L3 文档 | 不执行 | 需先确认 1.0 范围、发布对象、权限、审批、版本和回退合同 |
| 将 Evaluation 从 L2 提升到 L3 | 不执行 | 需具备可实现的数据合同、角色责任、运行边界和验收场景 |

## 7. 后续进入门槛

只有同时满足以下条件，才可以开始修改 Harness：

1. 修改项只是导航、映射、链接或术语对齐；若涉及 L2 节点，只能如实标注其成熟度，不得把它操作化为接口、状态机、原因码或发布流程。
2. 不改变现有对象状态、确认边界、事实写权限和成熟度。
3. 不复制系统总架构 Mermaid，不创建第二张主图。
4. 不把 Evaluation、Policy Release 或动态规则系统伪装成已确认的 1.0 L3 能力。
5. 修改后任一稳定状态写入路径仍唯一指向 Governed State Commit。

出现以下任一情况必须停止并重新收敛：

- 需要新增运行时对象、状态、原因码或发布接口。
- 需要让评估结果直接改变治理规则。
- 需要改变 Prompt、Harness、PRD 三者的真相源顺序。
- 同一架构节点找不到唯一职责归属。
- 同一状态生效动作出现多个写入入口。

## 8. 当前结论

目标架构的主体并没有要求重写 Harness。当前结果是：

- Agent Core 中的收敛、提交、Runtime 与工具底座，以及 State 中的权威记录主要已有 L3 支撑；对话行为、上下文装配、对象语义和工作区投影仍包含明确的 L2 合同。
- Domain & Harness Rules 是多个 Harness 分组的聚合视图，不应反向决定目录结构。
- User Interfaces 主要属于产品和技术边界，Harness 只约束其权限。
- Evaluation Control Plane 是唯一显著超出现有成熟度的部分，必须继续保持 L2 / TARGET，不得自动写成 L3。

本轮已完成 README、Overview、Main Runtime Loop 的架构映射，并补齐 System Boundaries、Prompt Control、Evaluation 与 Independent Evaluation 中会引发权限误读的边界说明。

当前不需要继续修改 Runtime、Memory、Tools、Governance、Observability 或 Verification 的既有合同。后续若要补 Failure Corpus、正式 Human Review 发布职责或 Versioned Policy / Prompt Release，必须作为新的 L2 -> L3 决策单独收敛，不能沿用本轮“术语和边界对齐”的授权直接实施。
