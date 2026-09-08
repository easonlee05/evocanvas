# Memory and State（记忆与状态）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi Session + EvoCanvas 结构化工作包`
> 当前实现状态：`合同已定，代码待迁移`
> 实现说明：Pi Session 保存过程；一个 Workspace 对应一个逻辑结构化工作包，工作包以不可变 Revision 保存稳定状态；不建立独立状态账本。

## 1. 控制目标

将“讨论过什么”和“现在稳定成立什么”分开保存，使 Pi、用户编辑、Canvas 和交接物始终基于同一套稳定状态。

## 2. 两类权威记录

| 记录 | 权威内容 | 不承担 |
| --- | --- | --- |
| Primary Pi Session | 原始 User / Assistant / Tool Entry、候选方案、推理过程、运行事件 | 当前稳定对象状态 |
| 结构化工作包 Revision | 已固定对象、关系、状态、来源引用、确认和交接指针 | 完整聊天记录、Canvas 布局、重复来源正文 |

Canvas、Toast、卡片位置、诊断视图和交接物渲染都是 Revision 的派生投影，不是第三类事实源。

## 3. 工作包和 Revision

- `1 Workspace = 1 logical structured package`。
- 每次完整稳定提交创建一个不可变 Revision。
- Revision 保存完整规范化对象图和提交元数据，不依赖重放增量事件恢复当前状态。
- 正文变化、关系变化、状态变化、确认变化和交接指针变化均产生新 Revision。
- 临时候选、未确认建议和比较过程只保留在 Session。
- 用户已经固定“这是一个尚未解决的问题”时，该问题可作为 `open` 对象进入工作包。

## 4. 统一提交入口

Pi 编辑和用户直接编辑使用同一语义提交能力：

```text
读取 base_revision_id
-> 提交受治理语义操作
-> 确定性校验与权限检查
-> 原子创建新 Revision
-> 更新 current_revision_id
-> 触发依赖复核标记和 Canvas 投影
```

用户直接编辑不先转成 Chat，也不自动唤起 Pi。Pi 下次运行通过最新 Revision 读取变化。

## 5. 身份、来源与确认

- 同一语义对象跨 Revision 保持 `object_id`。
- 实质替代创建新对象，并通过 `supersedes` 指向旧对象。
- 来源默认绑定到对象或关系；一个对象内有多个独立判断时可细化到判断级。
- 来源使用 `session_id + entry_id` 或外部稳定引用，不复制正文。
- 确认绑定具体内容哈希、对象范围、关系范围和基础 Revision，不能只绑定对象 ID。

## 6. 状态推进和过时

确定性依赖检查在每次提交后立即执行：

- 上游变化明确影响下游：下游标记 `review_required`，不自动改写结论。
- 确认内容哈希变化：原确认不再覆盖新内容。
- 交接关键依据失效：交接状态转为 `invalidated`。
- 是否影响无法确定：交接状态转为 `suspended` 并等待澄清。
- 无影响：保留交接有效状态和证据。

潜在语义影响由 Pi 在下一次对话中分析，不由提交器调用第二个模型。

## 7. 失败与恢复

- 版本冲突：拒绝提交，返回最新 Revision 和差异定位。
- 提交结果未知：按幂等键查询，不重复创建 Revision。
- 依赖检查失败：不得发布新 current 指针；整个提交回滚。
- Canvas 投影失败：Revision 保持有效，从当前 Revision 重建投影。
- Session 不可用：稳定工作包仍可读取；不可伪造缺失过程来源。
- 工作包不可用：可继续普通对话，但关闭稳定写入和交接确认。

## 8. L3 验收场景

1. 未确认方案在十轮对话后仍只存在于 Session，Canvas 不出现正式对象。
2. 用户确认“定价依据仍待验证”后，可提交一个 `open` 问题对象。
3. 两个客户端基于同一 Revision 并发修改，只有一个原子成功，另一方收到版本冲突。
4. 用户直接编辑上游约束后，下游决定标记 `review_required`，但正文不被自动重写。
5. Canvas 数据全部丢失后，可仅凭 current Revision 重建等价业务投影。

## 9. 子规格

- [Memory（记忆）](./01%20Memory%EF%BC%88%E8%AE%B0%E5%BF%86%EF%BC%89.md)
- [State Model（状态模型）](./02%20State%20Model%EF%BC%88%E7%8A%B6%E6%80%81%E6%A8%A1%E5%9E%8B%EF%BC%89.md)
- [Stable State and Handoff（稳定状态与交接）](./03%20Stable%20State%20and%20Handoff%EF%BC%88%E7%A8%B3%E5%AE%9A%E7%8A%B6%E6%80%81%E4%B8%8E%E4%BA%A4%E6%8E%A5%EF%BC%89.md)
- [Convergence Decisions（收敛决策基线）](./04%20Convergence%20Decisions%EF%BC%88%E6%94%B6%E6%95%9B%E5%86%B3%E7%AD%96%EF%BC%89.md)
