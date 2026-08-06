# Tool Contract（工具契约）

> 当前成熟度层级：`L3 可指导实现的治理规格层`
> 编码门槛：`可直接指导 ToolSpec、ToolCall、ToolResult、权限矩阵、重试与来源入链实现`

## 1. 职责边界

工具把外部读取、验证和转换能力接入 EvoCanvas，但不裁决事实地位，也不绕过统一提交器修改结构化包。

工具成功只表示调用完成，不表示：

- 来源已经可靠。
- 证据足以支持结论。
- 候选内容已经确认。
- 结构化状态已经提交。

## 2. 工具分类

1. 读取与验证工具：读取材料、检索历史、验证外部事实、定位引用。
2. 转换与分析工具：解析、分段、比对、抽取、冲突检测，不产生事实写入。
3. 结构整理工具：基于已有状态生成候选提案或确定性组装结构化包，不直接提交。
4. 外部副作用工具：正式发布、外发、写外部系统等；默认不进入 1.0 普通收敛路径。

统一提交器不是模型可自由调用的普通工具。它只接受已经通过验证与治理、携带版本和幂等键的内部提交请求。

## 3. 工具规格

每个工具规格至少包含：

| 字段 | 含义 |
| --- | --- |
| `name`、`version` | 稳定名称与版本 |
| `description` | 使用目的与边界 |
| `input_schema`、`output_schema` | 可机器校验的输入输出 |
| `capability_class` | 读取、转换、整理或外部副作用 |
| `side_effect` | `none / read / internal_write / external_write` |
| `allowed_runtime_units` | 允许在哪类运行单元调用 |
| `required_permissions` | 权限集合 |
| `timeout_seconds` | 超时 |
| `idempotency_mode` | 无副作用、调用方键控或工具自身幂等 |
| `retry_semantics` | 哪些错误可以重试 |
| `failure_semantics` | 失败后的结构化结果 |
| `event_semantics` | 必须产生的事件 |
| `sensitive_fields` | Trace 中需脱敏的字段 |

工具清单与当前权限通过 Runtime Developer Message 和 Tool Schema 动态注入；System Prompt 只保留不伪造结果、外部事实先验证等稳定原则。

## 4. 工具调用记录

一次调用至少记录：

| 字段 | 含义 |
| --- | --- |
| `tool_call_id` | 调用 ID |
| `tool_name`、`tool_version` | 工具身份 |
| `workspace_id`、`conversation_id`、`package_id` | 作用范围 |
| `chat_turn_id` 或 `convergence_run_id` | 所属运行单元 |
| `message_seq` 或消息范围 | 调用依据 |
| `arguments` 或安全摘要 | 入参；敏感字段需脱敏 |
| `idempotency_key` | 有副作用调用的幂等键 |
| `attempt` | 当前尝试次数 |
| `status` | 调用状态 |
| `started_at`、`completed_at` | 时间记录 |
| `error` | 结构化错误，可空 |

状态只允许：

```text
created / running / succeeded / failed / denied / timed_out / cancelled
```

## 5. 工具结果

工具结果至少包含：

| 字段 | 含义 |
| --- | --- |
| `tool_call_id` | 对应调用 |
| `status` | 最终状态 |
| `summary` | 简短可见摘要 |
| `data` 或 `data_ref` | 结构化结果或不可变指针 |
| `source_refs` | 可追溯来源 |
| `artifacts` | 产生的内部产物引用 |
| `error` | 结构化错误，可空 |
| `completed_at` | 完成时间 |

原始工具结果先保存为 `tool` 消息或不可变结果记录。收敛回合可以引用它形成来源、证据或候选，但不能改写原结果来制造结论。

工具返回的文本属于待分析数据。即使其中出现“忽略规则”“直接确认”等语句，也不获得指令权限。

## 6. 来源与证据入链

外部输入标准化为来源时，至少包含：

- `source_id`
- `source_type`
- `origin`
- `content_pointer`
- `imported_at`
- `scope`
- `integrity` 或内容指纹
- `reliability_hint`

工具结果被提升为证据时，至少包含：

- `evidence_id`
- `source_refs`
- `claim` 或观察项
- `excerpt_or_snapshot`
- `confidence`
- `conflict_flags`
- `created_in_turn` 或 `created_in_run`

`reliability_hint` 和 `confidence` 只辅助验证，不能自动授予确认地位。

## 7. 运行单元权限矩阵

| 运行单元 | 允许 | 不允许 |
| --- | --- | --- |
| Chat 回合 | 读取、检索、验证、来源定位 | 修改结构化包、改变对象状态、正式发布 |
| 收敛判断 | 默认不调用业务工具；必要时只读最小索引 | 生成对象、调用写工具、提交状态 |
| 收敛回合 | 读取、验证、转换、形成候选提案、确定性组包 | 绕过验证治理直接写事实、直接外发 |
| 统一提交器 | 按内部协议原子提交 | 接受自由文本指令、调用外部业务工具 |
| 投影器 | 消费已提交事件并更新画布、Todo、Toast | 反向修改事实状态 |

## 8. 读取工具与结构化工具

Chat 中的读取工具结果必须先作为原始 `tool` 消息保存。只有后续收敛引用了其中与当前主题相关的部分，它们才进入来源或证据链。

### 8.1 Source Resolver（来源解析器）

Source Resolver 是读取与验证类的只读能力，用于按已存在的 `source_ref` 和具体位置取回需要核对的原始片段。它不接受自由业务语义作为新来源，不总结原文，也不裁决信息地位。

最小输入包括 `source_ref`、位置或范围、期望内容指纹和读取上限；最小结果包括实际来源 ID、实际位置、原始片段或不可变数据引用、内容指纹、读取时间和结构化错误。

Source Resolver 的结果必须先保存为原始 `tool` 消息或不可变工具结果，再进入 Conversation History 与 Context Manifest。它不回填 Structured Package Input，不因读取成功而自动生成证据对象，也不因读取失败而改写已有包快照。

结构整理工具只能：

- 形成结构化候选。
- 校验 Schema。
- 根据既有结构化状态确定性组装包版本草稿。
- 生成提交请求所需的差异，不执行提交本身。

它不能通过“打包”重新解释已确认内容，也不能偷偷引入新事实。

## 9. 幂等、超时与重试

- 无副作用读取可以在暂时错误后自动重试。
- 转换工具可以在输入和工具版本不变时重试。
- 内部写入必须携带幂等键；结果未知时先查询原调用。
- 外部副作用工具默认禁止自动重试，除非工具明确保证幂等。
- 超时不等于失败已回滚；有副作用工具超时后必须先确认实际结果。
- 同一运行单元的调用次数和重试次数必须有可配置上限。

## 10. 事件要求

每次实际工具调用至少产生：

```text
tool.call.started
tool.call.succeeded
tool.call.failed
tool.call.denied
tool.call.timed_out
```

事件至少带：工具调用 ID、所属运行单元、工具名与版本、状态、尝试次数、耗时、错误码和脱敏后的结果摘要。

## 11. 失败处理

- 读取失败：保留缺口，Chat 可以说明无法验证；不得脑补结果。
- 转换失败：保留原材料和失败记录，可以在预算内重试。
- 权限拒绝：立即终止该调用，不用更高权限静默替代。
- 来源失效：对应证据不得继续支持新的稳定结论。
- 结构整理失败：不创建提交请求，不影响现有结构化包。
- 外部副作用结果未知：进入人工可见的待核对状态，不自动重放。

## 12. 与现有底座的迁移关系

现有 `ToolSpec`、`ToolCall`、`ToolResult` 和 `ToolPolicy` 可以继续作为基础类型，但需要补充：

- Workspace、会话、包和运行单元关联字段。
- 工具版本、调用尝试和幂等键。
- 超时、未知结果和脱敏字段。
- 基于 Chat、判断、收敛和提交器的权限，而不是旧角色与工作流步骤语义。

当前 `artifact.write` 等旧产物工具不得直接等同于结构化包提交器。

## 13. L3 验收场景

至少验证：

1. Chat 可以调用读取工具，但不能调用结构化状态写入。
2. 工具结果保存为原始 `tool` 消息，并能回指调用记录。
3. 未知工具、无权限工具和非法参数得到结构化拒绝。
4. 同一幂等键的内部写调用不会产生重复副作用。
5. 外部读取失败不会被模型补写成成功结果。
6. 工具结果中的指令文本不会覆盖 System 或 Developer 指令。
7. 结构整理工具只能生成候选或差异，不能直接提交。
8. 敏感参数不会原样进入事件和日志。
