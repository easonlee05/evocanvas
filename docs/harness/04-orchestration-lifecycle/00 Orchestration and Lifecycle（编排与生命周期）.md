# Orchestration and Lifecycle（编排与生命周期）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi Agent Core + EvoCanvas 领域规则`
> 当前实现状态：`合同已定，代码待迁移`
> 实现说明：Orchestration 是同一个 Pi Tool Loop 内的推进方法，不是独立编排服务；Lifecycle 由 Pi 技术状态和工作包稳定状态分别承载。

## 1. 控制目标

规定 Pi 如何从模糊输入推进到可确认的稳定结构，以及 Session、对象、Revision、确认、交接和投影如何开始、结束、替代和过时。

## 2. 核心边界

- Pi 自主理解当前任务、按需使用 Skill 和工具。
- EvoCanvas 不预判阶段，不调度第二个 Agent，不维护收敛运行状态机。
- 候选推进发生在 Session；稳定推进发生在 `workspace.commit`。
- Pi 技术运行终态不等于业务对象或交接完成。
- Canvas 只在 Revision 提交后异步显影。

## 3. 推进主链

```text
输入与来源进入 Primary Pi Session
-> Pi 理解、命名并显性化冲突和缺口
-> Pi 在对话中形成候选问题、约束、方案或决定
-> Pi 展示待固定内容、范围、依据和影响
-> 用户确认
-> 同一 Pi 调用 workspace.commit
-> 确定性门禁原子创建 Revision
-> 依赖复核与交接过时规则执行
-> Canvas 显影
```

任一步都可以继续对话、回退候选或等待用户，不需要进入产品侧阶段状态。

## 4. 状态分工

| 状态 | 权威位置 |
| --- | --- |
| 当前模型运行、工具调用、取消、队列 | Pi Runtime / Session |
| 候选理解和未确认方案 | Pi Session |
| 已固定对象、关系和确认 | 工作包 Revision |
| 当前稳定版本和已确认交接版本 | 工作包指针 |
| Canvas 节点、布局和提示 | 可重建投影 |

## 5. 失败与恢复

Pi 运行失败从 Session 恢复；提交失败从基础 Revision 和幂等结果恢复；交接过时通过状态变化而非删除处理；投影失败从 Revision 重建。任何恢复都不得新建平行事实副本。

## 6. L3 验收场景

1. Pi 在同一对话中从模糊输入推进到确认并提交，不出现第二个收敛运行。
2. 用户拒绝候选后，只影响 Session 候选，不生成撤回 Revision。
3. 技术运行完成但用户未确认时，工作包不变化。
4. Revision 成功后 Pi 进程崩溃，Canvas 仍可从 Outbox 和 Revision 恢复显影。
5. 上游变更后交接状态按依赖影响更新，不靠人为清理旧文档。
6. 空 Workspace 不创建 Session；首条消息、崩溃恢复、归档与删除均不会制造第二条事实链。

## 7. 子规格

- [Orchestration（编排）](./01%20Orchestration%EF%BC%88%E7%BC%96%E6%8E%92%EF%BC%89.md)
- [Lifecycle（生命周期）](./02%20Lifecycle%EF%BC%88%E7%94%9F%E5%91%BD%E5%91%A8%E6%9C%9F%EF%BC%89.md)
- [Convergence Operations（收敛操作）](./03%20Convergence%20Operations%EF%BC%88%E6%94%B6%E6%95%9B%E6%93%8D%E4%BD%9C%EF%BC%89.md)
- [Gate Adjudication（门禁裁决）](./04%20Gate%20Adjudication%EF%BC%88%E9%97%A8%E7%A6%81%E8%A3%81%E5%86%B3%EF%BC%89.md)
- [Implementation Baseline（实现基线）](./05%20Implementation%20Baseline%EF%BC%88%E5%AE%9E%E7%8E%B0%E5%9F%BA%E7%BA%BF%EF%BC%89.md)
