# Main Runtime Loop（运行主链）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi Agent Core + EvoCanvas 工具与投影`
> 当前实现状态：`原生运行主链已接入，恢复与边界待验证`
> 实现说明：只有一个长期 Pi Agent 主链；结构收敛是同一 Tool Loop 中的行为，不是第二运行类型。

## 1. 控制目标

给实现、测试和诊断提供唯一主链，防止 Chat、收敛、治理和 Canvas 各自推进一套状态。

## 2. 正常主链

```text
[1] User Submission(submission_id + content_hash) -> 创建/恢复 Primary Pi Session -> User Entry(entry_id)
[2] transformContext -> 最新稳定 Workspace Context Snapshot
[3] Pi -> 回答 / 追问 / 读 Skill / 读对象或来源 / 形成候选
[4] 若无稳定变更 -> Assistant Reply -> 结束本轮
[5] 若有稳定变更 -> 展示含义、范围、依据、影响
[6] 用户确认 -> User Entry
[7] Pi -> workspace.commit
[8] 提交器 -> 身份、版本、Schema、来源、确认、状态、依赖、幂等
[9] 原子创建完整 Revision -> 更新 current 指针
[10] Tool Result -> Pi Session；Pi 后续调用前重新 transformContext
[11] Projection Outbox -> Canvas Renderer -> projected Revision
[12] 可选交接确认 -> latest confirmed handoff 指针
```

## 3. 分支行为

- 直接回答：停在步骤 4，不创建业务状态。
- 多轮澄清：步骤 3 与用户输入循环，候选只在 Session。
- 用户拒绝：候选留在历史，不产生撤回 Revision。
- 用户直接编辑：界面直接进入步骤 8，使用同一提交器，不自动唤起 Pi。
- 只收录来源事实：在来源完整性门禁后可进入步骤 8，但不自动推导约束或决定。
- 外部行动：在步骤 10 后按需调用独立外部工具，并取得动作级授权。

## 4. 一致性边界

- Pi Main Lane 控制单一主动 Agent Loop。
- 工作包用 `base_revision_id` 控制并发。
- 提交用幂等键防重复 Revision。
- 外部工具用独立幂等键和实际回执判断副作用。
- Canvas 通过 `projected_revision_id` 判断是否最新。

## 5. 失败与恢复

- 模型失败且无工具成功：工作包不变。
- 提交失败：保留候选和确认记录引用，返回可恢复原因。
- 提交成功后运行取消：Revision 保留，停止后续工具。
- 投影失败：Revision 保留，Canvas 标记落后并重建。
- 外部结果未知：停止自动重试并先核对。

## 6. 权限与确认

Pi 可以选择下一步，但无权自我确认产品含义。稳定提交、交接确认和外部行动分别验证其确认范围；任何一个确认不能替代另一个。

## 7. 观测链

`submission_id -> session_id -> entry_id / turn_id -> invocation_id / tool_call_id -> operation_id -> commit_id -> revision_id -> projection_id`。用户直接编辑从 `actor_id + ui_action_id -> operation_id` 关联 Commit，不伪造 Pi Turn。

## 8. 验收场景

1. 一个完整流程中不存在第二 Agent Session 或独立收敛运行。
2. 未确认候选不会进入步骤 8。
3. 提交成功后 Pi 下一次模型调用读到新 Revision。
4. 取消发生在提交后时，Revision 与 Canvas 最终仍一致。
5. 用户直接编辑和 Pi 提交拥有相同版本、幂等和依赖行为。
6. 第一条消息重复提交只产生一个 Entry；未知外部效果不会被自动重放。
