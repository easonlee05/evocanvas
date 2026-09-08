# Tool Contract（工具契约）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi Tool Loop + EvoCanvas 工具 Schema / Hooks`
> 当前实现状态：`合同已定，代码待迁移`
> 实现说明：Pi 执行工具；EvoCanvas 定义领域效果、权限、确认、幂等和错误合同。

## 1. 控制目标

让 Pi 获得读取、稳定写入和外部行动能力，同时保证模型文本本身不能绕过权限或直接改变业务状态。

## 2. 工具类别

| 类别 | 示例 | 默认风险 |
| --- | --- | --- |
| 只读 | `workspace.get_object`、`session.read_entry`、`source.read` | 无业务写入 |
| 稳定语义提交 | `workspace.commit` | 改变工作包 Revision |
| 投影与诊断 | `canvas.rebuild`、`trace.query` | 不改变业务事实 |
| 外部副作用 | 发送、发布、创建外部任务等 | 改变外部系统 |

工具名可以按实现调整，但类别和治理合同不可缺失。

## 3. 通用 Schema

每个工具必须声明：

```text
name
version
description
input_schema
output_schema
required_capabilities[]
side_effect_class: none | workspace | external
confirmation_requirement
idempotency_behavior
timeout_behavior
replay: safe | never
error_codes[]
```

Runtime 注入主体、Workspace、Session、Turn 和 Tool Call 身份；模型不能从参数声明自己拥有更高权限。

## 4. 稳定提交工具

`workspace.commit` 输入至少包括：

```text
base_revision_id
idempotency_key
operations[]
confirmation_refs[]
change_summary
```

每个 `operations[]` 元素必须有独立 `operation_id`。它标识稳定业务操作，不得复用 Pi 的 `invocation_id / tool_call_id`。工具级 `idempotency_key` 标识整次提交请求；相同键必须绑定相同规范化请求哈希。

允许的 `operations` 是受治理语义操作，不允许整包自由覆写：

```text
create_object
update_object
change_status
supersede_object
create_relation
remove_relation
record_confirmation
confirm_handoff
suspend_handoff
invalidate_handoff
```

提交器原子执行 Schema、身份、来源、版本、确认范围、状态转换、依赖传播和幂等检查；全部通过后才创建新 Revision。

## 5. 确认规则

- 来源事实的完整性收录可在有稳定来源和身份时自动完成，但其外部真实性状态必须如实保存。
- Pi 推断的问题、约束、方案、决定及其作用范围必须绑定用户确认。
- 用户直接编辑本身构成该编辑主体对具体变更的确认，但不能替其他人确认外部副作用或超出权限的范围。
- 外部不可逆工具必须在执行前取得针对动作、目标和关键参数的明确授权；工作包确认不能代替该授权。

## 6. 幂等与结果

- 所有 workspace 和 external 副作用工具必须接受幂等键。
- 相同幂等键和相同请求返回原结果。
- 相同幂等键但内容不同返回 `tool.idempotency_conflict`。
- 超时或连接中断后先查询结果；不能确认时返回 `unknown`，不得自动重放不可逆动作。
- Tool Result 必须包含 `success | failed | unknown`、实际效果标识和可安全重试信息。

## 6.1 恢复重放分类

| `replay` | 适用工具 | 崩溃恢复 |
| --- | --- | --- |
| `safe` | 纯读取，或能以稳定幂等键查询并保证重复执行无新增效果的动作 | 先查原结果；确认未完成后可自动重放 |
| `never` | 外部不可逆动作、无权威幂等查询的动作、结果重复会新增效果的动作 | 不自动重放；结果未知时等待外部回执或人工核对 |

`success / failed / unknown` 是本次执行结果，`safe / never` 是工具静态恢复策略，二者不得混为一列。即使 `replay=safe`，在无法验证请求哈希或幂等记录时也不得自动重放。

## 7. 权限

工具执行前同时校验：主体身份、Workspace 访问权、所需能力、确认记录、目标资源和当前版本。权限拒绝不得通过换工具名、调用低层接口或让模型生成自由文本规避。

## 8. 失败与恢复

| 原因码 | 含义 |
| --- | --- |
| `tool.schema_invalid` | 输入不符合 Schema |
| `tool.permission_denied` | 主体无权执行 |
| `workspace.confirmation_required` | 缺少匹配内容和范围的确认 |
| `workspace.stale_revision` | 基础 Revision 过时 |
| `tool.idempotency_conflict` | 同键不同请求 |
| `tool.effect_unknown` | 无法确定是否产生副作用 |
| `tool.source_unavailable` | 必需来源无法读取 |
| `tool.internal_failure` | 可归因的内部失败 |

失败 Tool Result 进入 Session；不得把异常吞掉并返回看似成功的自然语言。

## 9. 观测要求

记录工具版本、输入摘要哈希、Runtime 注入身份、权限结论、确认引用、开始结束时间、实际结果、幂等键和关联 Revision / 外部效果 ID。敏感正文按安全策略脱敏，但身份与结果不可丢失。

## 10. 验收场景

1. 模型伪造 `actor_id=owner` 时，Runtime 注入身份覆盖或拒绝该字段。
2. 未确认候选决定调用 `workspace.commit`，返回 `workspace.confirmation_required`。
3. 相同提交因网络超时被重试，只产生一个 Revision。
4. 外部发送动作超时且结果未知时，不自动再次发送。
5. 只读来源工具返回失败时，Pi 不声称已读取正文。
6. `operation_id` 与 `invocation_id` 不同，但可通过提交审计双向关联。
7. `replay=never` 的调用在结果未知时不会因 Session 恢复而再次执行。
