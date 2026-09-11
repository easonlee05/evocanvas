# Runtime and Tools（运行时与工具）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi Agent Core + EvoCanvas 工具能力`
> 当前实现状态：`原生运行时与工具链已接入，完整验证待补齐`
> 实现说明：Pi 原生管理 Agent Loop、Session、流式、取消、压缩和技术 Trace；EvoCanvas 只提供领域工具及其确定性治理。

## 1. 控制目标

保证所有对话、推理和工具调用都运行在同一个 Pi 核心中，同时确保只有受治理的工具结果能改变稳定工作包或产生外部副作用。

## 2. 职责边界

| 能力 | 归属 |
| --- | --- |
| 模型调用、Tool Loop、消息、流式、取消、重试、窗口和压缩 | Pi Agent Core |
| Primary Session、分支、Entry 和技术运行 Trace | Pi Agent Core |
| 结构化工作包读取与语义提交工具 | EvoCanvas 能力装入 Pi |
| 对象、来源、确认、版本和幂等门禁 | EvoCanvas 工具 Schema / Hooks |
| Canvas 投影 | EvoCanvas Renderer |
| 产品语义裁决 | 当前 Pi 提议，用户确认 |

不建立外部 Product Kernel、独立运行状态机或 `ChatTurn / ConvergenceRun` 持久对象。

## 3. 主链

```text
Primary Pi Session 收到 User Entry
-> Pi 进入正常 Agent Tool Loop
-> 按需读 Skill、工作包、历史和来源
-> 直接回复，或展示待确认的稳定变更
-> 用户确认后调用 workspace.commit
-> 工具确定性校验并原子创建 Revision
-> Pi 读取提交结果并回复
-> Renderer 异步显影 Revision
```

## 4. 权威结果

- Pi Session Entry 是运行过程真相。
- Tool Result 是工具实际执行真相。
- 工作包 Revision 是稳定业务状态真相。
- 外部系统回执是外部副作用真相。
- Pi 的自然语言总结、Canvas 和 Toast 均不能替代上述权威结果。

## 5. 失败边界

技术调用失败只改变本次运行结果，不自动改变业务状态；工作包提交成功后即使回复或投影失败，Revision 仍有效。外部副作用结果未知时必须先核对，不得把超时当成未执行。

## 6. L3 验收场景

1. 一次对话内读取来源、确认和提交都出现在同一 Pi Session / Tool Loop。
2. 模型生成了正确 JSON 但未实际调用提交工具时，工作包不改变。
3. 提交成功后回复流断开，重新读取仍能发现新 Revision。
4. Canvas 投影失败不会回滚已提交 Revision。
5. 运行取消后不会留下半可见 Revision 或未记录的外部副作用。
6. 第一条用户消息因网络重试重复到达时只产生一个 User Entry；不同身份层不会共用同一 ID。
7. 进程在工具返回前崩溃时，只自动恢复 `replay=safe` 的调用；`replay=never` 且结果未知的调用停在人工核对。

## 7. 子规格

- [Runtime（运行时）](./01%20Runtime%EF%BC%88%E8%BF%90%E8%A1%8C%E6%97%B6%EF%BC%89.md)
- [Tool Contract（工具契约）](./02%20Tool%20Contract%EF%BC%88%E5%B7%A5%E5%85%B7%E5%A5%91%E7%BA%A6%EF%BC%89.md)
- [Failure and Recovery（失败与恢复）](./03%20Failure%20and%20Recovery%EF%BC%88%E5%A4%B1%E8%B4%A5%E4%B8%8E%E6%81%A2%E5%A4%8D%EF%BC%89.md)
