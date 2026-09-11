# Observability（可观测性）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi Trace + Revision 审计元数据 + Canvas 投影检查点`
> 当前实现状态：`原生可观测性已接入，追溯闭环待验证`
> 实现说明：不复制 Pi 的运行 Trace；EvoCanvas 通过稳定关联标识把运行、提交、交接和投影串成一条可查询链。

## 1. 控制目标

当结果错误、缺失或过时时，能够回答：用户说了什么、Pi 看到了什么、用了哪些规则和来源、调用了什么工具、哪个确认使什么内容生效、生成了哪个 Revision、Canvas 显影到哪里。

## 2. 三类权威观测记录

| 记录 | 负责内容 |
| --- | --- |
| Pi Session / Technical Trace | Entry、模型、Skill、工具、重试、取消、Token、技术终态 |
| Revision / Confirmation Metadata | 稳定操作、主体、来源、确认、Policy、依赖和交接变化 |
| Projection Checkpoint | 投影目标 Revision、渲染版本、结果和失败 |

诊断视图只联结和解释这些记录，不成为新的事件真相源。

## 3. 最小关联键

```text
workspace_id
submission_id
session_id
entry_id / turn_id
invocation_id / tool_call_id
operation_id
commit_id
revision_id
confirmation_id
handoff_id
projection_id / projected_revision_id
```

每层只保存其实际拥有的标识；通过显式外键关联，不复制整段消息或完整工作包。

## 4. 观测事件

至少覆盖：上下文装配、Skill 读取、工具调用、权限和确认拒绝、提交结果、依赖传播、交接状态变化、投影结果、恢复与重放。事件必须有稳定 code、时间、主体、关联键和脱敏结果摘要。

## 5. 用户可见与内部可见

- 用户看到必要的状态变化、风险、失败原因和恢复动作。
- 开发诊断可看到完整关联链和技术细节。
- 敏感来源正文和密钥不因 Trace 默认暴露。
- “成功”只依据权威工具或 Revision 结果显示，不依据 Pi 自然语言。

## 6. 失败与恢复

Trace 写入失败不得静默：对稳定提交和高风险外部动作，必要审计无法保存时应在执行前拒绝；对普通只读或对话可降级执行并报告观测缺口。诊断索引丢失可由权威记录重建。

## 7. L3 验收场景

1. 从 Canvas 卡片可追溯到 Revision、提交、确认、Tool Call 和用户 Entry。
2. Pi 回复声称提交成功但无 Tool Result / Revision 时，诊断显示未提交。
3. 投影落后能准确识别目标和已投影 Revision。
4. Trace 索引删除后可从 Pi Trace、Revision 和投影检查点重建。
5. 无审计能力时外部不可逆动作被拒绝而非静默执行。
6. 重复 User Submission 能定位到同一 Entry，稳定操作与工具调用身份不会混淆。

## 8. 子规格

- [Projection Signals（显影提示）](./01%20Projection%20Signals%EF%BC%88%E6%98%BE%E5%BD%B1%E6%8F%90%E7%A4%BA%EF%BC%89.md)
- [Trace Model（追踪模型）](./02%20Trace%20Model%EF%BC%88%E8%BF%BD%E8%B8%AA%E6%A8%A1%E5%9E%8B%EF%BC%89.md)
- [Diagnostic Views（诊断视角）](./03%20Diagnostic%20Views%EF%BC%88%E8%AF%8A%E6%96%AD%E8%A7%86%E8%A7%92%EF%BC%89.md)
