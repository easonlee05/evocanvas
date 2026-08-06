# Implementation Baseline（实现基线）

> 当前成熟度层级：`L3 可指导实现的治理规格层`
> 编码门槛：`可作为 1.0 编排接口、原因码、状态终态、迁移任务和验收测试的实现输入`

## 1. 实现边界

编排与生命周期不新增平行运行时。实现必须复用运行时层已经定义的：

- 原始消息记录。
- `ChatTurn`。
- `ConvergenceJudgement`。
- `ConvergenceRun`。
- `CommitAttempt`。
- 包级租约、待重新判断水位、状态账本、Outbox 和投影器。

本层只补充触发归并、提案操作、信息地位门禁和各记录之间的连接规则。

## 2. 最小能力单元

| 能力单元 | 输入 | 输出 | 禁止事项 |
| --- | --- | --- | --- |
| 判断入口 | 完成的 Chat、来源导入、语义编辑或恢复请求 | `skip / defer / trigger` 和原因码 | 生成业务对象 |
| 调度器 | 判断结果、包级租约、待重判水位 | 一个可执行收敛回合或更新后的水位 | 同包并发写回合 |
| 提案生成器 | 基础包版本、消息范围、必要来源 | 最小结构化操作集合 | 自行写状态或伪造引用 |
| 验证与门禁适配 | 提案操作、来源、确认引用和治理政策 | 允许、降级或拒绝的操作集合 | 发送第二条 Assistant 回复 |
| 提交协调 | 已放行操作、期望版本、`operation_id` | 原子提交结果 | 部分写入或盲目重试 |
| 投影触发 | 已提交 Outbox 事件 | 画布、Todo、里程碑和 Toast 更新 | 反向修改事实状态 |

这些是职责边界，不要求对应为同名类、进程或服务。

## 3. 最小原因码与配置

### 3.1 判断原因码

至少支持：

```text
no_semantic_delta
weak_semantic_delta
source_imported
explicit_organize
candidate_identified
conflict_identified
confirmation_detected
semantic_edit
handoff_requested
stale_recheck
```

### 3.2 正常结束原因

至少支持：

```text
already_covered
no_committable_change
insufficient_confirmation_scope
insufficient_source
conflict_preserved
rejected_by_governance
```

`base_version_changed` 不是业务正常结束原因；版本检查失败进入技术 `stale`（见 §4）。

**原因码 → 业务结果映射：**

| 原因码 | 业务结果 | 说明 |
| --- | --- | --- |
| `already_covered` | `no_change` | 增量已被当前包覆盖 |
| `no_committable_change` | `no_change` | 无新业务语义或结构变化 |
| `insufficient_confirmation_scope` | `not_ready` | 有待升级目标但确认不足 |
| `insufficient_source` | `not_ready` | 有待升级目标但来源不足 |
| `conflict_preserved` | `applied` | 冲突已作为候选或标记提交 |
| `rejected_by_governance` | `rejected_by_governance` | 治理裁决拒绝 |

`no_change` = 无可推进目标；`not_ready` = 有目标但条件未满足。

**具体判定时机（提案生成步骤完成后）：**

```
提案生成结果
├── 产出零个可提交目标 → no_change（原因码 already_covered 或 no_committable_change）
└── 产出一个或多个目标
    ├── 所有目标均被验证 / 门禁拒绝 → not_ready（原因码 insufficient_confirmation_scope 或 insufficient_source）
    └── 至少一个目标被放行 → applied（其余目标可降级）
```

`no_committable_change`（无新内容）与 `already_covered`（已被包覆盖）保留为两个独立原因码，均映射 `no_change`，不合并。

### 3.3 可配置参数

以下参数必须可配置、可记录、可回放，但不作为产品不变量：

- 连续消息短合并窗口。
- 弱信号累积阈值。
- 是否调用小模型的规则阈值。
- 提案结构修复次数与时间预算。
- 租约时长和恢复扫描间隔。

**基线默认值（初版起点，上线后按评测调整）：**

| 参数 | 默认值 |
| --- | --- |
| 连续消息短合并窗口 | 5 秒 |
| 弱信号累积阈值 | 3 条消息 |
| 调用小模型阈值 | 强信号直接触发；弱信号 ≥ 2 条才调用 |
| 提案结构修复次数上限 | 2 次 |
| 提案时间预算 | 10 秒 |
| 收敛租约时长 | 30 秒 |
| 心跳续租间隔 | 10 秒 |
| 恢复扫描间隔 | 15 秒 |

每次实际使用的参数版本必须写入 trace，保证可回放。收敛租约的续租与过期判定规则见 [Runtime §6](../03-runtime-tools/01%20Runtime%EF%BC%88%E8%BF%90%E8%A1%8C%E6%97%B6%EF%BC%89.md#6-并发与租约)。

## 4. 提交前必检

每次可写收敛回合在提交前至少检查：

1. `input_through_seq` 之后是否出现改变语义范围的新消息。
2. `expected_state_version` 是否仍等于实际版本。
3. `expected_package_version` 是否仍等于当前版本。
4. 所有来源和确认消息引用是否真实存在且属于允许范围。
5. 每个信息地位升级是否拥有匹配的确认依据。
6. 部分放行后的操作依赖是否仍然完整。
7. `operation_id` 是否已经提交。

任一版本检查失败（规则 2、3）时，以 `base_version_changed` 为原因整次提交进入技术 `stale`，不得把部分结果写入当前包。

## 5. 迁移边界

当前迁移必须消除以下旧模型：

- 用工作区级 `active_turn` 阻塞新的 User 消息或返回 `409`。
- 让普通包更新进入 `confirmation_queue` 或 `awaiting_confirmation`。
- 让 Chat 服务直接修改结构化包。
- 把“打开问题 -> 收束结构 -> 裁决去向”实现成第二套复杂回合状态机。
- 把画布卡片、Toast 或固定变化摘要当作确认入口。
- 每轮 Chat 都创建包版本或调用收敛大模型。

现有通用事件、工具、会话、持久化和错误基础设施继续复用；只替换旧产品流程适配层。

## 6. L3 验收场景

### 6.1 普通讨论不触发写入

用户继续讨论但没有形成新结构增量。Chat 正常完成，判断返回 `skip` 或 `defer`，不创建包版本，也不出现 Toast。

### 6.2 候选自动整理

用户明确表达“CSV 是候选，Excel 仍需评估”。收敛可以创建待决策候选和未决项，不要求用户确认“是否生成卡片”，画布显影为候选状态。

### 6.3 已有 Chat 确认直接生效

Assistant 明确复述“1.0 只支持 CSV”，User 回答“对，就这样”。收敛验证范围后，在同一原子提交中创建决策并标记已决定，不生成第二次确认请求。

### 6.4 含糊表达不得升级

User 只说“可以考虑 CSV”。收敛最多保留候选；若没有可提交候选变化，则以 `not_ready` 结束。

### 6.5 同包并发

收敛运行期间又收到新消息。新消息正常进入 Chat，调度器推进待重判水位；旧回合提交前发现语义范围或版本变化后进入 `stale`，不自动重跑。

### 6.6 交接草稿与已确认版本并存

新信息使当前包产生交接草稿更新，但用户尚未确认。`current_version` 前进，`latest_confirmed_version` 保持不变；画布可以显示当前草稿和旧确认版本的可用性差异。

### 6.7 外部动作单独门禁

包版本已确认后，用户要求正式发布到外部系统。系统仍执行外部副作用门禁；不得仅凭包已确认自动外发。

### 6.8 投影可恢复

事实提交成功但画布投影失败。包版本和状态账本保持成功，投影器通过 Outbox 重放或当前版本重建恢复，不重复提交事实。

## 7. 设计禁令

- 不新增阶段状态机、确认任务或复杂回合运行记录。
- 不把判断器变成业务对象生成器。
- 不让提案模型决定版本号、消息 ID 或确认真伪。
- 不把候选自动整理误写成候选自动生效。
- 不因后台失败阻塞后续正常 Chat。
