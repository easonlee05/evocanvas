# EvoCanvas Harness 宪法文档集

这组文档不是对当前后端实现的解释，也不以现有代码结构作为事实来源。

它们的目的只有一个：

- 用 ETCLOVG 作为设计框架，指导 EvoCanvas 1.0 如何被构造成一个可治理、可验证、可追溯、可交接的 AI Agent 产品。

阅读顺序建议如下：

1. `docs/harness/00-system-view.md`
2. `docs/harness/G-governance.md`
3. `docs/harness/V-verification.md`
4. `docs/harness/L-lifecycle-orchestration.md`
5. `docs/harness/C-context-memory.md`
6. `docs/harness/T-tool-interfaces.md`
7. `docs/harness/O-observability.md`
8. `docs/harness/E-execution-environment.md`

然后再按需查阅其他分层文档。

## 文档清单

- `docs/harness/00-system-view.md`
  - 总体系统视角，定义 EvoCanvas 的 Harness 总目标、系统边界、主状态推进逻辑与分层关系。
- `docs/harness/E-execution-environment.md`
  - E 层：执行环境，定义受控运行单元、隔离边界、失败恢复和写入边界。
- `docs/harness/T-tool-interfaces.md`
  - T 层：工具接口，定义输入接入协议、外部能力接入协议和工具使用边界。
- `docs/harness/C-context-memory.md`
  - C 层：上下文与记忆，定义上下文分层、复水策略、稳定记忆与冷历史。
- `docs/harness/L-lifecycle-orchestration.md`
  - L 层：生命周期与编排，定义收敛状态机、中断点、阶段推进与角色分工。
- `docs/harness/O-observability.md`
  - O 层：可观测性，定义 turn trace、proposal trace、治理痕迹与来源追溯。
- `docs/harness/V-verification.md`
  - V 层：验证，定义结构验证、策略验证、来源验证和独立评估职责。
- `docs/harness/G-governance.md`
  - G 层：治理，定义事实分层、风险分级、生效规则、确认规则和裁决边界。

## 使用方式

这组文档适合被当作 4 类工作输入：

- 产品设计输入：用于判断某项功能是否符合 EvoCanvas 1.0 的产品目标。
- 架构设计输入：用于定义对象、状态机、接口协议和系统边界。
- 工程排期输入：用于决定应先做哪些控制能力，再做哪些效率能力。
- 测试设计输入：用于从治理规则和状态推进逻辑反推测试清单。

## 核心立场

- EvoCanvas 不是文档生成器，也不是自由聊天框。
- EvoCanvas 的核心不是让 AI 直接给结论，而是让 AI 在受控边界内推动状态收敛。
- 因此，Harness 的第一职责不是增强生成，而是约束生成、验证生成、追溯生成，并把生成结果转化为结构化工作状态。

