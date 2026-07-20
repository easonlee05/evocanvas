# Runtime（运行时）

> 当前成熟度层级：`L3 可指导实现的治理规格层`
> 编码门槛：`可直接指导 Chat、判断器、收敛调度器、提交器与运行记录的第一批实现和测试`

## 1. 职责边界

运行时负责：

- 持久化原始消息并维护顺序。
- 运行正常 Chat，并保证回复顺序。
- 低成本判断是否值得启动收敛。
- 调度受控收敛并限制并发。
- 通过版本校验和幂等提交保护事实状态。
- 记录可观察结果、失败和因果链。

运行时不负责：

- 把产品旅程实现成阶段状态机。
- 让 Chat 直接修改结构化包。
- 替验证层判断结构质量。
- 替治理层宣布内容生效。
- 把画布或 Toast 当作事实来源和确认入口。

## 2. 原始消息记录

每条 `user / assistant / tool` 消息独立保存，至少包含：

| 字段 | 含义 |
| --- | --- |
| `message_id` | 消息唯一标识 |
| `workspace_id` | 所属工作区 |
| `conversation_id` | 所属会话 |
| `message_seq` | 会话内单调递增序号 |
| `role` | `user / assistant / tool` |
| `content` 或 `content_ref` | 原文或不可变内容指针 |
| `tool_call_id` | 工具消息关联调用，可空 |
| `created_at` | 持久化时间 |
| `metadata` | 模型、来源和附件等非事实元数据 |

消息序号用于顺序和版本边界，时间戳只用于展示与诊断。运行时不得把多条原始消息改写成一条伪造历史。

## 3. 四类运行记录

### 3.1 Chat 回合记录

一个 Chat 回合可以承接一条或一组连续 User 消息，并产生至多一条主 Assistant 回复。

最小字段：

| 字段 | 含义 |
| --- | --- |
| `chat_turn_id` | Chat 回合 ID |
| `workspace_id`、`conversation_id` | 运行范围 |
| `package_id`、`base_package_version` | 回答时读取的结构化包 |
| `input_from_seq`、`input_through_seq` | 本轮 User 输入消息范围 |
| `assistant_message_id` | 完成后的主回复消息，可空 |
| `status` | 运行状态 |
| `created_at`、`started_at`、`completed_at` | 时间记录 |
| `error` | 结构化错误，可空 |

运行状态只允许：

```text
queued -> running -> completed
                  -> failed
                  -> cancelled
```

Chat 回合没有“等待结构化确认”状态。用户确认发生在正常对话中，并作为后续收敛的来源依据。

### 3.2 收敛判断记录

判断记录回答“当前消息变化是否值得启动一次收敛”，不生成业务对象。

最小字段：

| 字段 | 含义 |
| --- | --- |
| `judgement_id` | 判断 ID |
| `chat_turn_id` | 主要触发 Chat 回合 |
| `workspace_id`、`package_id` | 判断范围 |
| `from_message_seq`、`through_message_seq` | 被判断消息范围 |
| `base_state_version`、`base_package_version` | 判断时读取版本 |
| `signal_level` | `none / weak / strong` |
| `decision` | `skip / defer / trigger` |
| `reason_codes` | 可枚举原因码 |
| `used_small_model` | 是否调用小模型 |
| `created_at`、`evaluated_at` | 时间记录 |
| `error` | 结构化错误，可空 |

`skip` 表示没有有效结构变化；`defer` 表示继续积累；`trigger` 表示可以创建收敛回合。判断结果不是事实状态，也不能直接产生画布变化。

### 3.3 收敛回合记录

收敛回合负责把消息与当前结构化包整理为可验证提案，并在满足条件时申请提交。

最小字段：

| 字段 | 含义 |
| --- | --- |
| `convergence_run_id` | 收敛回合 ID |
| `judgement_id` | 触发判断，可空但必须有显式触发来源 |
| `workspace_id`、`conversation_id`、`package_id` | 运行范围 |
| `input_from_seq`、`input_through_seq` | 使用的消息边界 |
| `base_state_version`、`base_package_version` | 基础版本 |
| `status` | 技术运行状态 |
| `result_type` | 业务处理结果 |
| `proposal_ref` | 结构化提案引用，可空 |
| `operation_id` | 提交幂等键，可空 |
| `attempt_count` | 当前尝试次数 |
| `created_at`、`started_at`、`completed_at` | 时间记录 |
| `error` | 结构化错误，可空 |

运行状态与业务结果必须分开：

```text
运行状态：created / queued / running / validating / committing /
          completed / failed / stale / cancelled

业务结果：applied / no_change / not_ready / rejected_by_governance
```

`not_ready` 表示当前内容还不足以升级相应信息地位。它不会通过第二条 Assistant 消息追问，而是把缺口留给后续正常 Chat 引导。

### 3.4 提交尝试记录

每一次事实提交都必须有独立记录：

| 字段 | 含义 |
| --- | --- |
| `commit_attempt_id` | 提交尝试 ID |
| `convergence_run_id` | 所属收敛回合 |
| `operation_id` | 全局幂等键 |
| `commit_kind` | `content / governance`，正文提交或纯治理提交 |
| `expected_state_version` | 期望结构化状态版本 |
| `expected_package_version` | 期望包版本 |
| `actual_state_version`、`actual_package_version` | 提交时实际版本 |
| `result_state_version`、`result_package_version` | 成功后的版本，可空 |
| `status` | 提交结果 |
| `outbox_event_ids` | 事务内登记事件 |
| `created_at`、`completed_at` | 时间记录 |
| `error` | 结构化错误，可空 |

提交状态只允许：

```text
started / applied / duplicate / stale / failed / unknown
```

## 4. 主运行链

### 4.1 正常 Chat

1. 先持久化 User 消息并分配 `message_seq`。
2. 创建 Chat 回合并读取当前结构化包与相关历史消息。
3. 按会话顺序生成主 Assistant 回复；读取类工具结果保存为原始 `tool` 消息。
4. 持久化 Assistant 回复并结束 Chat 回合。
5. 创建或更新后置判断请求。

用户输入不得因后台收敛、待处理投影或旧提案返回“当前工作区忙”。同一会话的回复生成可以串行排队，但消息接收不能被拒绝。

### 4.2 后置判断

判断采用“规则预筛 + 必要时小模型”的方式：

1. 无业务增量内容直接 `skip`，例如礼貌确认、继续、纯措辞修正。
2. 有新想法但尚不足以形成结构变化时 `defer`，继续累积。
3. 出现明确冲突、约束、决策确认、可结构化缺口或显式整理要求时可以 `trigger`。

逻辑上每个完成的 Chat 都经过判断，但不代表每次都调用小模型，更不代表每次都启动收敛。

### 4.3 收敛调度

判断命中后，调度器先进入可配置的短合并窗口。窗口内的新消息扩展待判断范围，而不是立即创建多个回合。

真正启动前至少检查：

- 当前是否已有同包收敛回合。
- 判断使用的包版本是否仍然有效。
- 当前积累是否仍满足触发条件。

精确时间窗口和语义阈值属于评测参数，不写成产品不变量，但必须可配置、可记录并可回放。

### 4.4 收敛执行

1. 装配当前结构化包、指定消息范围和必要来源。
2. 形成结构化提案，不直接改写事实。
3. 执行结构验证、来源验证、策略验证和风险分类。
4. 治理层决定哪些信息地位可以更新。
5. 有有效变化时交给统一提交器；无变化或未准备好时正常结束。

“足够收敛”不表示所有问题都已经解决，而是表示当前已知、未知、冲突、候选或确认内容已经清楚到可以按正确信息地位写入包。

## 5. 判断频率与待重新判断水位

当同包收敛回合运行时又产生新消息，系统维护唯一的待重新判断水位：

| 字段 | 含义 |
| --- | --- |
| `package_id` | 所属包 |
| `from_message_seq` | 尚未消费范围起点 |
| `through_message_seq` | 当前最新范围终点 |
| `strongest_signal` | 合并期间最强触发信号 |
| `updated_at` | 最近更新时间 |

原始消息仍独立保存。水位只合并“稍后再判断一次”的调度请求，不生成摘要、不改变消息内容。

当前收敛回合进入终态后，调度器针对水位覆盖的最新范围只判断一次。该判断可以继续 `skip` 或 `defer`，因此不等于自动重跑旧回合。

## 6. 并发与租约

- 并发键为 `(workspace_id, package_id)`，不是整个工作区的全局 Chat 锁。
- 同一并发键同时最多一个处于 `running / validating / committing` 的收敛回合。
- 收敛租约至少记录持有者、获得时间和到期时间；默认租约时长 30 秒，运行期间每 10 秒续租一次（重置到期时间），心跳失败不中断回合但记录告警；最后一次续租后超过租约时长仍无心跳即判定过期，进程失联后由恢复器处理。恢复器默认每 15 秒扫描过期租约，发现后先按 `operation_id` 幂等核对提交是否已完成：未完成则标记回合为 `stale` 并释放租约，由最新水位触发新判断；已完成则释放租约并补跑遗漏的 Outbox。
- Chat 不持有收敛租约，用户可以继续输入。
- 任何晚于 `input_through_seq` 的新消息都会使当前回合在提交前版本检查失败；短合并窗口负责减少无意义过期。
- 卡片语义编辑、包状态变化和其他受控写入同样推进结构化状态版本。

当前代码中的工作区级 `active_turn` 可以作为迁移期互斥手段，但不是 L3 目标模型，也不得继续阻塞新 User 消息。

## 7. Chat 确认与结构化写入

Chat 负责把问题聊清楚，也承载用户的明确确认。专门的收敛部件负责把已形成的理解写入结构化包。

例如用户明确说“确定，本周只做 CSV，其他格式放下一期”，该原始消息就是确认依据。后续收敛可以在验证作用范围后直接写入已完成决策，不再创建第二次审批。

如果用户只说“可以考虑 CSV”，收敛只能保留为候选或未决，不能升级成已确认决策。

因此普通结构化整理不使用独立确认队列，也不存在长期占用运行权的 `awaiting_confirmation`。独立审批只适用于正式外发、外部副作用或其他不可逆动作，不属于普通包版本更新。

## 8. 幂等原子提交

统一提交器采用“当前快照 + 追加式状态账本 + 版本校验”的事务，并区分两种提交内容。

正文提交 `content`：

```text
检查 operation_id 是否已提交
检查 expected_state_version
检查 expected_package_version
写入新的结构化状态快照
创建不可变 package_version
追加状态账本记录
推进 current_version
登记 Outbox 事件
原子提交
```

纯治理提交 `governance`：

```text
检查 operation_id 是否已提交
检查目标 package_version、expected_state_version 与 expected_package_version
记录确认、过时或风险标注
追加包版本治理账本事件
必要时移动 latest_confirmed_version
登记 Outbox 事件
原子提交
```

纯治理提交不修改对象正文，不创建内容相同的新 `package_version`，也不推进 `current_version`。两类提交共用同一幂等、并发校验、事务和 Outbox 边界。

规则：

- 相同 `operation_id` 重复提交时返回原提交结果，不创建第二个版本。
- 任一期望版本不匹配时，整次提交为 `stale`，不得部分写入。
- 正文提交中的状态快照、包版本、账本、版本指针和 Outbox 必须一起成功或一起失败；纯治理提交中的确认记录、治理账本、相关指针和 Outbox 也必须一起成功或一起失败。
- 提交结果未知时先按 `operation_id` 查询，禁止盲目重试。
- Outbox 在事务提交后发布；发布失败可以重放，不回滚事实提交。
- 画布、Todo 和 Toast 消费提交事件，投影失败后可以重建。

文件存储阶段可以通过包级锁、临时文件、提交清单和原子替换模拟事务；数据库阶段应使用真实事务和唯一约束。

## 9. 失败与自动恢复边界

允许在同一运行记录内自动重试：

- 暂时性模型或网络错误。
- 幂等读取工具失败。
- 尚未进入提交阶段的结构输出校验失败，且仍有修复预算。

不得自动重跑：

- 已过期收敛回合。
- 治理明确拒绝的提案。
- 已知事实冲突。
- 结果未知但尚未查询 `operation_id` 的提交。
- 可能造成外部重复副作用的工具调用。

完整恢复规则见 [Failure and Recovery（失败与恢复）](./03%20Failure%20and%20Recovery%EF%BC%88%E5%A4%B1%E8%B4%A5%E4%B8%8E%E6%81%A2%E5%A4%8D%EF%BC%89.md)。

## 10. 运行事件

Runtime 至少产生以下事件：

```text
chat.turn.started / completed / failed
convergence.judgement.completed / failed
convergence.run.started / completed / failed / stale
state.commit.started / applied / duplicate / stale / failed / unknown
projection.requested
```

事件公共字段至少包含：

- `event_id`
- `workspace_id`
- `conversation_id`
- `package_id`
- `chat_turn_id`、`judgement_id`、`convergence_run_id`、`operation_id` 中适用的字段
- `message_seq` 或消息范围
- `state_version`、`package_version` 中适用的字段
- `created_at`
- `payload`

事件用于追踪、通知和投影，不替代领域记录。

## 11. 与现有底座的迁移关系

继续复用：

- `Event`、`TraceSpan` 与事件总线。
- `ToolSpec`、`ToolCall`、`ToolResult` 与工具策略。
- `DomainError`。
- 模型调用与工具桥接适配器。
- 通用持久化、锁和原子文件替换能力。

不直接复用为主领域模型：

- 带旧工作流步骤语义的 `Task`。
- 带旧 Agent 角色与目标语义的 `AgentSession`。
- 同步执行规划、提案、治理和应用的 `CanvasService.start_turn()`。
- 工作区级 `active_turn` 与 `awaiting_confirmation`。

旧能力通过适配器逐步迁移，不要求为了达到 L3 文档一次性重写全部代码。

## 12. L3 验收场景

至少验证：

1. 后台收敛运行时仍能接收并保存新 User 消息。
2. 连续短消息只触发一次合并后的判断。
3. 无业务增量消息不调用小模型、不启动收敛。
4. 同包不能同时提交两个收敛结果。
5. 新消息或状态变化使旧回合提交为 `stale`。
6. 相同 `operation_id` 重复提交只产生一个包版本。
7. 提交成功但事件发布失败时，Outbox 可以补发。
8. Chat 中已有明确确认时，收敛直接写入正确信息地位，不二次审批。
9. 确认不足时只保留候选或未决，不伪装成已确认。
10. 画布投影失败不会回滚已提交事实，并可从事件重建。
