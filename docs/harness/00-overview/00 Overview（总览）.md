# Overview（总览）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi Agent Core + EvoCanvas 产品能力 + Canvas 显影`
> 当前实现状态：`原生主链已接入，完整闭环证据待补齐`
> 实现说明：本总览定义十二项 Harness 的共同地基和实现边界；每项细则以对应 L3 文档为准。

## 1. 控制目标

EvoCanvas Harness 的最高目标是：**降低需求从模糊输入、对话理解、结构固定到下游交接之间的失真。**

它不是为了让模型生成更多内容，也不是为了建立 Pi 之外更复杂的流程。成功必须表现为：冲突和未决可见、稳定判断可追溯、确认范围准确、过时交接被拦截、下游误解和返工减少。

## 2. 统一架构地基

1. Pi Agent Core 是唯一 Agent 运行核心。
2. 空 Workspace 可以没有 Session；第一条真实消息后，一个 Workspace 对应一个长期 Primary Pi Session。
3. EvoCanvas 以 System Instructions、Skills、结构化工作包工具、治理 Hooks 和 Canvas Renderer 装入 Pi。
4. Pi Session 保存原始过程；结构化工作包不可变 Revision 保存稳定业务状态。
5. 用户与 Pi 共用同一语义提交能力。
6. 候选内容留在 Session；只有来源完整性记录和经确认的语义变更进入工作包。
7. Canvas 只显影已提交 Revision，不参与事实裁决。
8. 结构化交接物是已确认 Revision 的派生视图。
9. 不建立 Pi 外部 Product Kernel、Supervisor、独立收敛运行、平行历史、Context Manifest 或状态账本。
10. 用户入口、Session Entry、稳定操作和工具调用使用不同身份；工具恢复策略与执行结果分开表达。

## 3. 十二项 Harness

```text
Harness
= Instructions + Context + Memory
+ Runtime + Tools + Orchestration + Lifecycle
+ Safety + Governance
+ Observability + Verification + Evaluation
```

| 方法 | 控制问题 | 目标实现归属 |
| --- | --- | --- |
| Instructions | Pi 应如何理解、判断和行动 | EvoCanvas 方法装入 Pi |
| Context | Pi 当前基于什么工作 | Pi Session + transformContext |
| Memory | 过程和稳定状态如何保存 | Pi Session + 工作包 Revision |
| Runtime | Agent 如何可靠执行和恢复 | Pi Agent Core |
| Tools | 如何读取、写入和产生副作用 | Pi Tool Loop + EvoCanvas 工具 |
| Orchestration | 同一个 Pi 如何选择并推进下一步 | Pi 原生 Tool Loop，不是新组件 |
| Lifecycle | 各类记录如何开始、结束和过时 | Pi 技术状态 + 工作包稳定状态 |
| Safety | 如何防止误导、越权和危险效果 | Pi 保护 + 工具护栏 |
| Governance | 什么内容和动作何时生效 | 用户裁决 + 确定性提交器 |
| Observability | 如何追溯、回放和归因 | Pi Trace + Revision 审计 + 投影检查点 |
| Verification | 单次过程和结果是否满足合同 | 确定性验证器 |
| Evaluation | 系统长期是否降低需求失真 | 离线评估控制面 |

Pi 不是第十三项方法；它是多项方法的统一实现底座。

## 4. 权威记录

| 问题 | 权威答案 |
| --- | --- |
| 用户、Pi、工具实际发生过什么 | Primary Pi Session / Technical Trace |
| 当前稳定对象、关系和确认是什么 | `current_revision_id` 指向的工作包 Revision |
| 下游默认可使用哪个交接 | `latest_confirmed_handoff_revision_id` |
| 外部动作是否成功 | 外部工具回执和幂等查询 |
| Canvas 当前显示什么 | Projection Checkpoint |

自然语言回复、摘要、Toast、Canvas 布局和诊断视图均不能取代这些权威记录。

## 5. 稳定主链

```text
感觉或材料进入 Primary Pi Session
-> Pi 理解、追问、显性化冲突和未决
-> Pi 形成候选并向用户展示待固定含义与范围
-> 用户确认
-> 同一 Pi 调用 workspace.commit
-> 确定性治理和验证原子创建 Revision
-> 依赖与交接影响更新
-> Canvas 显影稳定 Revision
-> 用户可确认交接 Revision 供下游使用
```

来源事实可在完整性检查后收录；Pi 推断的问题、约束、方案和决定必须经用户确认。用户可以接受未验证前提，但其状态和风险必须持续显式保留。

## 6. L3 统一门槛

每项方法和子规格必须明确：

1. 控制目标；
2. 实现归属；
3. 权威输入输出；
4. 权限与确认边界；
5. 状态推进、回退和过时；
6. 失败与恢复；
7. 可执行的验收场景。

达到 L3 表示实现者无需自行发明产品规则；不表示代码已经完成。当前实现状态必须与方法成熟度分别记录。

## 7. 目录

- [System Boundaries（系统边界）](./01%20System%20Boundaries%EF%BC%88%E7%B3%BB%E7%BB%9F%E8%BE%B9%E7%95%8C%EF%BC%89.md)
- [Core Object Model（核心对象模型）](./02%20Core%20Object%20Model%EF%BC%88%E6%A0%B8%E5%BF%83%E5%AF%B9%E8%B1%A1%E6%A8%A1%E5%9E%8B%EF%BC%89.md)
- [Main Runtime Loop（运行主链）](./03%20Main%20Runtime%20Loop%EF%BC%88%E8%BF%90%E8%A1%8C%E4%B8%BB%E9%93%BE%EF%BC%89.md)
- [Maturity Levels（成熟度层级）](./04%20Maturity%20Levels%EF%BC%88%E6%88%90%E7%86%9F%E5%BA%A6%E5%B1%82%E7%BA%A7%EF%BC%89.md)
- [Convergence Readiness（收敛就绪度）](./05%20Convergence%20Readiness%EF%BC%88%E6%94%B6%E6%95%9B%E5%B0%B1%E7%BB%AA%E5%BA%A6%EF%BC%89.md)
