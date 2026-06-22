# EvoCanvas Harness 宪法文档集

> 当前整体判断：`文档集整体处于 L2 向 L3 过渡阶段`
> 编码门槛：`仅 G 层、L 层已达到可直接指导第一批实现的 L3；其余层默认仍按未到 L3 处理`

这组文档不是对当前后端实现的解释，也不以现有代码结构作为事实来源。

它们的目的只有一个：

- 用系统控制框架（ETCLOVG）作为设计框架，指导 EvoCanvas 1.0 如何被构造成一个可治理、可验证、可追溯、可交接的 agent 产品。

## 文档组织规范

为避免 harness 文档继续膨胀成单文件堆积，后续各层默认统一采用以下组织规范：

- 每一层使用同名文件夹承载，而不是继续使用单个层级 `.md` 文件；例如：`docs/harness/G-governance/`
- 每一层必须有一份主文档，默认排在该文件夹第一位，文件名采用：
  - `00 English Name（中文名）.md`
  - 例如：`00 Governance（治理）.md`
- 主文档负责讲框架、主干关系、运行主链、层内边界与展开入口，不应退化成纯索引页
- 子文档只负责展开主文档中某个已经出现、且确实需要单独讲清的问题
- 子文档文件名默认采用：
  - `01 English Name（中文名）.md`
  - `02 English Name（中文名）.md`
  - 依此类推
- 子文档排序必须按照它们在主文档正文中第一次出现的顺序排列
- 主文档中的子文档链接不应集中堆在文末；应放在对应正文章节中，每个展开点只放一个最直接的链接
- 如果某个层级暂时还没有拆出子文档，也仍建议先使用文件夹结构，为后续扩展预留稳定位置

这套规范的目标不是追求目录美观，而是保证：

- 主文档先建立整体心智
- 子文档只做必要展开
- 文件树顺序与阅读顺序一致
- 后续扩写时不再反复推翻文档结构

阅读顺序建议如下：

1. `docs/harness/00-system-view/`
2. `docs/harness/G-governance/00 Governance（治理）.md`
3. `docs/harness/V-verification/`
4. `docs/harness/L-lifecycle-orchestration/00 Lifecycle Orchestration（生命周期与编排）.md`
5. `docs/harness/C-context-memory/`
6. `docs/harness/T-tool-interfaces/`
7. `docs/harness/O-observability/`
8. `docs/harness/E-execution-environment/`

然后再按需查阅其他分层文档。

## 文档清单

- `docs/harness/00-system-view/`
  - 总体系统视角，定义 EvoCanvas 的 Harness 总目标、系统边界、主状态推进逻辑与分层关系。
- `docs/harness/E-execution-environment/`
  - E 层：执行环境，定义受控运行单元、隔离边界、失败恢复和写入边界。
- `docs/harness/T-tool-interfaces/`
  - T 层：工具接口，定义输入接入协议、外部能力接入协议和工具使用边界。
- `docs/harness/C-context-memory/`
  - C 层：上下文与记忆，定义上下文分层、复水策略、稳定记忆与冷历史。
- `docs/harness/L-lifecycle-orchestration/00 Lifecycle Orchestration（生命周期与编排）.md`
  - L 层主文档：生命周期与编排框架、四个一级模块、主阶段骨架与展开入口。
- `docs/harness/L-lifecycle-orchestration/01 Stage Progression（阶段推进）.md`
  - 阶段推进器、五段主流程、检查点、停留规则与重判闭环。
- `docs/harness/L-lifecycle-orchestration/02 Gate Adjudication（门禁裁决）.md`
  - 高影响动作、事实边界门禁、确认请求与确认后顺序。
- `docs/harness/L-lifecycle-orchestration/03 State Ledger（状态账本）.md`
  - 状态账本最小记录范围、关键未决、非阻塞提醒与尾项摘要。
- `docs/harness/L-lifecycle-orchestration/04 Handoff Orchestration（交接编排）.md`
  - 结构化交接物（structured handoff）的编排规则、条目治理与草稿 / 正式边界。
- `docs/harness/O-observability/`
  - O 层：可观测性，定义回合追踪（turn trace）、提案追踪（proposal trace）、治理痕迹与来源追溯。
- `docs/harness/V-verification/`
  - V 层：验证，定义结构验证、策略验证、来源验证和独立评估职责。
- `docs/harness/G-governance/00 Governance（治理）.md`
  - G 层主文档：治理框架、主干关系与扩展文档导航。
- `docs/harness/G-governance/01 Runtime Baseline（运行基线）.md`
  - 治理目标、总原则、最小运行规则集与实现视角摘要。
- `docs/harness/G-governance/02 Facts and Risk（事实与风险）.md`
  - 事实分层、风险分级与冲突治理规则。
- `docs/harness/G-governance/03 Object Governance（对象治理）.md`
  - 核心结构化对象的生效、升级、回退与并存规则。
- `docs/harness/G-governance/04 Handoff Governance（交接物治理）.md`
  - 结构化交接包（handoff package）的最小治理规范与编排规则。
- `docs/harness/G-governance/05 Authority and Guardrails（权限与护栏）.md`
  - 确认机制、裁决权模型、多角色权限边界、治理回执与设计禁令。

## 使用方式

这组文档适合被当作 4 类工作输入：

- 产品设计输入：用于判断某项功能是否符合 EvoCanvas 1.0 的产品目标。
- 架构设计输入：用于定义对象、状态机、接口协议和系统边界。
- 工程排期输入：用于决定应先做哪些控制能力，再做哪些效率能力。
- 测试设计输入：用于从治理规则和状态推进逻辑反推测试清单。

## 成熟度层级与编码门槛

为避免在 harness 尚未收稳时过早进入实现，当前文档集统一采用以下成熟度层级：

- `L1 产品原则层`
  - 已明确产品目标、系统边界、第一性原则
  - 但对象、状态与治理条件仍较粗
- `L2 对象与流程定义层`
  - 已明确核心对象、主生命周期、关键流转关系
  - 但仍以概念规则为主，尚不足以直接约束实现
- `L3 可指导实现的治理规格层`
  - 已明确对象最小字段集、升级门槛、回退条件、关键状态边界
  - 已足以指导第一批实现、接口设计与最小验证
- `L4 可直接编码的运行时规格层`
  - 已进一步沉淀为结构模式（schema）、状态枚举、转换表、验证器规则、日志与回执字段
  - 可直接作为稳定实现与测试基线

当前规则是：

- 只有达到 `L3` 的模块，才允许直接进入主实现编码
- 低于 `L3` 的模块，优先继续沉淀 harness 规则，而不是直接扩写主流程代码
- 达到 `L3` 后，可以先写第一批实现；不要求等待整个 harness 全部达到 `L4`

对后续 AI 协作，统一增加以下要求：

- 任何新增、改写或重组 harness 文档的动作，都应同步判断受影响模块当前处于 `L1 / L2 / L3 / L4` 哪一层
- 如果层级发生变化，应在相关文档中同步更新层级判断或门槛说明
- 如果某模块尚未达到 `L3`，后续 AI 不应把它当作“可直接稳定编码”的既成规格
- 如果某模块已达到 `L3`，后续 AI 可以开始实现，但仍应在实现中继续为其向 `L4` 沉淀保留结构空间

## 核心立场

- EvoCanvas 不是文档生成器，也不是自由聊天框。
- EvoCanvas 的核心不是让 AI 直接给结论，而是让 AI 在受控边界内推动状态收敛。
- 因此，Harness 的第一职责不是增强生成，而是约束生成、验证生成、追溯生成，并把生成结果转化为结构化工作状态。
