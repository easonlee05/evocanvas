# Pi Runtime Contract（Pi 运行时接口契约）

> 状态：阶段 0 合同草案，供 Python 与 TypeScript 同步实现和合同测试
>
> 适用分支：`codex/pi-runtime-core-refactor`
>
> 依据：[Pi 重构设计](../../plans/2026-08-13-evocanvas-pi-runtime-core-refactor-design.md)、[Runtime L3](../harness/03-runtime-tools/01%20Runtime（运行时）.md)、[Tool Contract L3](../harness/03-runtime-tools/02%20Tool%20Contract（工具契约）.md)、[Convergence Operations L3](../harness/04-orchestration-lifecycle/03%20Convergence%20Operations（收敛操作）.md)

本文件冻结 Python Product Kernel 与私有 TypeScript Pi Runtime 之间的最小产品合同。它不把 Pi 的内部消息类、事件枚举、Provider 对象或供应商原生请求暴露给产品层，也不把仍处于 L2 的 Context Assembly 选择逻辑提前硬编码成跨语言事实。

机器可读的 v1 草案位于：[schemas/pi-runtime/v1-contracts.json](./schemas/pi-runtime/v1-contracts.json)。Schema 与本文件冲突时，以本文件引用的 L3 Harness 为准，先修合同再写实现。

阶段 0 的状态、Provider、工具、错误恢复和迁移基线见：[Pi Runtime Phase 0 Matrices](./06%20Pi%20Runtime%20Phase%200%20Matrices（Pi%20运行时阶段%200%20矩阵）.md)。

## 1. 控制权与事实源

| 能力或状态 | 唯一拥有者 | Pi 权限 |
| --- | --- | --- |
| User / Assistant / Tool 原始消息 | Python Message Store | 只消费本次调用副本 |
| `ChatTurn`、`ConvergenceJudgement`、`ConvergenceRun`、`CommitAttempt` | Python Runtime Store | 不持久化 |
| `package_id`、PackageVersion、Card、Relation、Handoff | Python Domain / Repository | 禁止读取和写入产品数据库 |
| Verification、Governance、Governed State Commit、Ledger、Outbox | Python Product Kernel | 禁止绕过 |
| Canvas、Todo、Handoff 投影 | Python Projection | 不可反向成为事实 |
| Provider、模型调用、技术重试、工具循环、取消、流式事件、usage | Pi Runtime | 只保留单次运行内存和短 TTL 终态查询 |

Pi 只能返回 Assistant 回复、判断结果或结构化收敛提案。提案不是事实写入；Python 必须重新验证来源、消息范围、版本、确认和治理策略后，才可以提交。

## 2. 产品侧窄接口

生产代码只允许一个真实实现 `PiRuntimeClient`。测试可以注入 Fake，但 Fake 必须实现相同的 `AgentExecutionPort`，不得保留第二个真实模型执行器。

```python
class AgentExecutionPort(Protocol):
    async def run_chat(self, request: ChatRunRequest) -> ChatRunResult: ...
    async def run_judgement(
        self, request: JudgementRunRequest
    ) -> JudgementRunResult: ...
    async def run_convergence(
        self, request: ConvergenceRunRequest
    ) -> ConvergenceRunResult: ...
    async def cancel(self, run_id: str) -> CancelResult: ...
```

接口方法只表达 EvoCanvas 产品需要的三类运行和取消，不提供 `run(dict)`、任意 Provider 选择或任意工具执行方法。

## 3. 公共请求基线

所有运行请求均使用以下公共字段；每类请求还必须带自己的业务范围字段。

| 字段 | 必填 | 约束 |
| --- | --- | --- |
| `schema_version` | 是 | 当前为 `pi-runtime.request.v1` |
| `run_id` | 是 | Python 生成；全局唯一；重试同一回合不得静默换 ID |
| `run_kind` | 是 | `chat / judgement / convergence` |
| `workspace_id` | 是 | 只用于关联和 Tool Token 绑定，不授权 Pi 读存储 |
| `conversation_id` | 是 | 对话边界；Chat 回复顺序由 Python 保证 |
| `package_id` | Chat/Convergence 必填；Judgement 在有包时必填 | 绑定当前活跃主题；不能用工作区代替包身份 |
| `from_message_seq`、`through_message_seq` | 是 | 会话内单调序号范围；包含本次语义依赖的 `user / assistant / tool` 原始消息 |
| `context_manifest` | 是（规则预筛除外） | 只读装配证据；见 §4，不复制完整 Prompt 或包正文 |
| `instructions_ref` | 是 | System、Runtime Developer、输出 Schema 和工具集版本引用；具体内容由 Python 组装 |
| `model_policy` | 是 | 产品级策略，不暴露供应商对象 |
| `tool_profile` | 是 | 运行类型、工具白名单、调用预算和结果上限 |
| `deadline_ms` | 是 | 从 Pi 收到请求开始计算的相对预算；不得超过 Python 侧总截止时间 |
| `trace_context` | 是 | `trace_id / request_id / parent_run_id` 等关联信息 |
| `idempotency_key` | 是 | 初始值通常等于 `run_id`；重复创建必须返回原运行状态或明确冲突 |
| `runtime_inputs` | 否 | Python 为本次调用装配的临时输入快照；只供 Pi 消费，不进入运行记录、Manifest 或产品事实 |

请求不得携带 Provider 凭证。密钥只存在 Pi Runtime 进程环境中。

`runtime_inputs` 若存在，至少包含 `structured_package_input`、`conversation_messages` 和可选的 `raw_user_message`。它是 Python 已选定输入面的短期传输副本：Python 负责选择、排序、范围和裁剪，Pi 只负责协议映射与模型调用；运行终止后不保留该快照，也不把它当作第二事实源。

## 4. Context Manifest 边界

Context Assembly 当前仍是 L2。这里冻结的只是模型调用所需的最小装配证据，不冻结“如何选择历史、如何排序、如何压缩”的产品算法。

`context_manifest` 至少包含：

```text
context_manifest_id
request_kind: chat | judgement | convergence
package_ref: package_id / package_version / state_version
structured_package_input_ref: id / content_hash
message_scope: from_seq / through_seq / history_compaction_ref / raw_user_message_ref
source_refs
instruction_and_schema_refs
included_sections
omissions
assembly_policy_version
budget_ref
degradation_flags
content_hashes
transport_ref: provider_id / adapter_version / protocol_version / capability_profile_version
```

约束：

- Manifest 只保存引用、版本、范围、裁剪结果和哈希，不保存完整 Prompt、包正文或供应商原生请求。
- 同一推进链中 Chat、模型判断和收敛必须引用相同的 `structured_package_input_ref`；纯规则预筛不伪造 Manifest。
- Adapter 只能把五个逻辑输入面映射到供应商原生临时请求，不得重新选择上下文、合并 Structured Package Input 与 Runtime Developer Message 或改写 Raw User Message。
- `runtime_inputs` 中的用户原话必须作为独立 User Message 原样传递；结构化包输入和历史消息保持来源边界，Adapter 不得用引用字符串替代正文。
- Manifest 缺少关键包版本、消息范围或来源时，Pi 可以继续 Chat，但 Python 必须关闭依赖缺口的稳定写入。

## 5. 三类运行请求与结果

### 5.1 Chat

请求额外字段：

```text
raw_user_message_ref
assistant_reply_schema_ref
conversation_order_key
```

结果：

```text
run_id
assistant_message: { content_blocks: [...] }
finish_reason: completed | length | tool_failed | cancelled | error
events_summary
usage
model_identity
context_manifest_id
```

`assistant_message` 只表示候选回复，不包含可自动提交的领域操作。Python 只在收到完整终态后保存一条主 Assistant 消息；未完成流片段不得触发收敛判断。

如果运行以取消、超时或错误结束，`assistant_message` 必须为 `null`；Python 不得用流片段或错误文案伪造正式回复。

### 5.2 Judgement

请求额外字段：

```text
chat_turn_id
base_state_version
base_package_version
signal_summary_ref
```

结果：

```text
run_id
decision: skip | defer | trigger
reason_codes: [string]
through_message_seq
confidence: number | null
usage
model_identity
context_manifest_id
```

规则可以在 Python 内直接返回 `skip / defer / trigger`，不调用 Pi；规则预筛不生成模型调用记录或 Manifest。

### 5.3 Convergence

请求额外字段：

```text
convergence_run_id
base_state_version
base_package_version
proposal_schema_ref
proposal_capture_tool_ref
```

结果：

```text
run_id
proposal: ConvergenceProposal | null
finish_reason: completed | not_ready | tool_failed | cancelled | error
tool_trace
usage
model_identity
context_manifest_id
```

提案必须由 `submit_convergence_proposal` 工具在 Pi 内捕获并通过 Schema 校验，不能从自然语言正文猜测。Pi 崩溃或终态不可查询时，Python 将本次运行视为失败/未知，禁止使用半条提案提交。

## 6. ConvergenceProposal 合同

提案是 Python 验证与治理的输入，不是提交请求。整个提案至少包含：

```text
proposal_schema_version
proposal_id
run_id
package_id
from_message_seq
through_message_seq
base_state_version
base_package_version
operations[]
```

每个 `operation` 至少包含：

```text
operation_id: 临时操作引用，由 Python 最终确定幂等键
operation_type
target_object_id: 新增时为空
temporary_target_ref: 新增对象的临时引用
before_ref: 更新前对象或版本引用，可空
payload: 类型化字段差异
source_refs[]
confirmation_refs[]
unresolved_refs[]
risk_level: low | medium | high
reason_codes[]
atomic_group_id: 可空
```

系统必须补齐或核实：真实对象 ID、版本号、消息/来源/确认引用、`operation_id`、原子依赖组和提交权限。模型不得伪造这些确定性字段。

操作类型沿用 L3 Convergence Operations：来源收录、缺口显性化、冲突保留、候选整理、结构维护、信息地位变化、替代与过时。未确认的约束提议不得仅凭提案升级为已生效约束；待决策候选、冲突和待澄清必须保留正确的信息地位。

治理结果与 Pi 结果分离：

| Python 业务结果 | 含义 |
| --- | --- |
| `applied` | 至少一个操作通过验证和治理并原子提交 |
| `no_change` | 没有新语义变化或当前包已覆盖 |
| `not_ready` | 有目标但来源/确认/范围不足 |
| `rejected_by_governance` | 治理拒绝，未提升信息地位 |

`stale`、`duplicate`、`unknown` 是提交/技术结果，不是 Pi 的业务结果。

## 7. HTTP 端点

Pi Runtime 只监听私有地址（开发默认 `127.0.0.1:8790`）。除健康检查外，所有端点需要内部鉴权；浏览器不得直接调用。

| 方法 | 路径 | 请求 | 响应 |
| --- | --- | --- | --- |
| `POST` | `/v1/chat-runs` | `ChatRunRequest` | `200 application/x-ndjson` 事件流 |
| `POST` | `/v1/judgement-runs` | `JudgementRunRequest` | `200 application/x-ndjson` 事件流 |
| `POST` | `/v1/convergence-runs` | `ConvergenceRunRequest` | `200 application/x-ndjson` 事件流 |
| `GET` | `/v1/runs/{run_id}` | `?after_sequence=<n>` 可选 | 当前运行摘要；断流后查询完整终态 |
| `POST` | `/v1/runs/{run_id}/cancel` | `CancelRequest` | `CancelResult` 或终态摘要 |
| `GET` | `/healthz` | 无 | 进程存活，不代表可接流量 |
| `GET` | `/readyz` | 无 | Provider、模型能力和配置均满足时 `ready` |
| `GET` | `/v1/capabilities` | 无 | 版本化能力矩阵 |

### 7.1 HTTP 状态与错误封套

业务错误必须使用稳定 `error_code`，不能依赖异常文案：

```json
{
  "schema_version": "pi-runtime.error.v1",
  "error_code": "run_id_conflict",
  "category": "input_error",
  "message": "safe human-readable summary",
  "retryable": false,
  "run_id": "run_...",
  "trace_id": "trace_...",
  "details": {}
}
```

| HTTP | 适用 | Python 行为 |
| --- | --- | --- |
| `400` | Schema、参数、期限或工具配置非法 | 标记输入错误，不重试 |
| `401/403` | 内部鉴权或 Run Token 无效 | 权限拒绝，不提升权限 |
| `404` | 终态已过期或 run 不存在 | 运行结果未知，按 `run_id` 核对 Python 记录 |
| `409` | 相同 `run_id` 的请求参数不一致 | 不启动第二次执行，记录冲突 |
| `429` | Pi 自身并发/预算上限 | 在 Python 总预算内有限重试 |
| `5xx` | Pi/Provider 技术故障 | 分类为暂时错误或引擎不可用 |

### 7.2 运行状态查询与断流

- 同一 `run_id` 重复创建且请求摘要相同：返回原运行摘要或继续事件，不启动第二次模型执行。
- 请求摘要不同：返回 `409 run_id_conflict`。
- Python 记录最后收到的 `sequence` 仅用于诊断和断流判断，不把事件当产品事实。
- Convergence 断流后必须先 `GET /v1/runs/{run_id}` 查询完整终态；查询不到完整提案时不得提交。
- Pi 进程重启后不恢复产品事实。若终态不在短 TTL 内，Python 将运行标记为技术失败或未知，等待安全重试/恢复器处理。

### 7.3 取消

`CancelRequest`：

```text
run_id
reason_code
requested_by
trace_context
```

取消是幂等的：已终态运行返回原终态；活动运行停止模型和工具循环，发出 `run.cancelled`，Python 记录 `cancelled`。取消与完成竞态时，以 Pi 先写入的终态为准，Python 不凭客户端超时猜测。

## 8. NDJSON 事件合同

每行一个 JSON 对象，媒体类型为 `application/x-ndjson`。`sequence` 在单个 `run_id` 内从 `1` 开始单调递增；重试或断流查询不得复用新序号。

公共封套：

```json
{
  "schema_version": "pi-runtime.event.v1",
  "event_id": "evt_...",
  "run_id": "run_...",
  "sequence": 3,
  "timestamp": "2026-08-14T00:00:00Z",
  "type": "assistant.completed",
  "trace_context": {"trace_id": "trace_...", "request_id": "req_..."},
  "payload": {}
}
```

事件类型与最低要求：

| 事件 | `payload` 最低字段 | 事实边界 |
| --- | --- | --- |
| `run.started` | `run_kind`、`model_identity`、`context_manifest_id` | 技术开始，不创建产品状态 |
| `assistant.delta` | `content_delta`、`delta_index` | 不可单独保存为正式回复 |
| `assistant.completed` | `assistant_message`、`finish_reason` | Python 收到完整终态后才可保存 |
| `tool.requested` | `tool_call_id`、`tool_name`、`tool_version`、参数安全摘要 | 需要 Python Tool Gateway 授权 |
| `tool.completed` | `tool_call_id`、`status`、`source_refs`、结果摘要 | 原始结果入 Tool 消息/记录 |
| `proposal.captured` | `proposal_id`、Schema 版本、操作数 | 仍是内存提案，不是事实 |
| `usage.updated` | `input_tokens`、`output_tokens`、`provider_usage_ref` | 用量/技术事件，不是产品事实 |
| `run.completed` | `result_ref`、`finish_reason`、`usage` | Python 可查询完整终态 |
| `run.cancelled` | `reason_code` | 不产生正式回复/提案 |
| `run.failed` | `error_code`、`retryable` | Python 分类恢复 |

未知事件类型可以记录但不能破坏主链；未知字段必须向前兼容，缺失必填字段必须明确失败。

## 9. Pi → Python Tool Gateway

Pi 不直接访问工作区、文件系统、数据库或公网。只读工具调用发送到 Python 内部 Gateway：

```text
POST /internal/v1/tool-calls
Authorization: Run <run-scoped-token>
```

请求至少包含：

```text
schema_version
tool_call_id
tool_name
tool_version
run_id
run_kind
workspace_id / conversation_id / package_id
message_seq 或 message_range
arguments
attempt
trace_context
```

结果至少包含：

```text
tool_call_id
status: succeeded | failed | denied | timed_out | cancelled
summary
data 或 data_ref
source_refs
artifacts
error
completed_at
```

首版白名单：`source.resolve`、`material.read`、`knowledge.retrieve`、`structure.validate`、`submit_convergence_proposal`（仅 Convergence）。禁止 Shell、代码执行、任意文件写、任意网络、任意 MCP 写和直接修改 Package/Card/Relation/Handoff/Confirmation/Ledger。

Run-scoped Token 必须绑定 `run_id`、工具白名单、workspace/conversation/package 范围、消息范围（若本次运行已冻结）、到期时间和最大调用次数；不能跨运行、跨消息范围或跨工具复用。令牌、Provider 凭证和敏感参数不得写入事件或普通日志。

## 10. Python 生命周期与提交边界

四类 Python 运行记录及其关键状态：

| 记录 | 技术状态 | 业务结果 |
| --- | --- | --- |
| `ChatTurn` | `queued / running / completed / failed / cancelled` | 无；最多一条主 Assistant 回复 |
| `ConvergenceJudgement` | 记录型判断 | `skip / defer / trigger` |
| `ConvergenceRun` | `created / queued / running / validating / committing / completed / failed / stale / cancelled` | `applied / no_change / not_ready / rejected_by_governance` |
| `CommitAttempt` | `started / applied / duplicate / stale / failed / unknown` | 提交技术结果 |

Convergence 在 Python 中固定执行：

```text
锁定 message range + package/state version
  -> 接收并校验 Pi proposal
  -> Schema / object / source / message / confirmation verification
  -> Governance 裁决与部分放行
  -> operation_id 幂等检查
  -> 提交前重新检查版本和消息水位
  -> 原子写入 PackageVersion + Ledger + Outbox
  -> 投影 Canvas / Todo / Handoff
```

任一基础版本或语义消息范围变化，整次回合进入技术 `stale`，不得部分写入。提交结果未知时按 `operation_id` 查询，禁止更换幂等键盲目重放。

## 11. Capability 与 Provider 兼容边界

Pi Runtime 的 `/v1/capabilities` 必须返回版本化能力记录，至少包含：

```text
runtime_version
pi_agent_core_version
pi_ai_version
node_version
provider_id
adapter_version
protocol_version
capability_profile_version
supported_run_kinds[]
structured_output
tool_calling
streaming
cancellation
usage_reporting
```

首批正式 Provider/协议支持矩阵必须至少覆盖 OpenAI Responses API 与 Anthropic Messages API，并经过统一的一致性、工具往返、结构化输出、流式事件、停止原因、用量、错误归一化和 Trace 关联测试后才可标记 `supported`。Pi 内部可先用 Fake Provider；未通过矩阵的兼容网关不得静默进入正式支持。

## 12. 安全、可观测与数据最小化

- Pi 端口不对公网或浏览器开放；健康检查与运行端点分离鉴权。
- Python 与 Pi 统一携带 `trace_id`、`request_id`、`run_id`、`workspace_id`、`conversation_id`、`chat_turn_id / convergence_run_id`、`operation_id`。
- Trace 至少可串联 `chat_turn → judgement → convergence_run → proposal → operation → commit_attempt`，并关联 `context_manifest_id`、`model_call_id`、provider/adapter/capability 版本和来源/确认/版本信息。
- 不记录 Provider 密钥、Run Token、完整上下文、用户材料全文或供应商原生请求/响应载荷。
- 结果大小、工具次数、重试次数、单次运行时间和 NDJSON 事件数量必须有上限。

## 13. 阶段 0 合同测试清单

在阶段 1/2 开始前，必须把以下场景转成 Python/TS 共享 fixture 或等价合同测试：

1. 三类请求的必填、枚举、长度和 nullable 校验。
2. 相同 `run_id` 重复创建返回原状态；参数不一致返回 `409`。
3. NDJSON 分片、粘包、重复序号、未知字段和未知事件。
4. 断流后 `GET /v1/runs/{run_id}` 可查询完整终态；查询不到提案时禁止提交。
5. 取消、超时、Provider 不可用、工具拒绝、结构化输出失败和结果未知。
6. Proposal operation 缺少来源/确认/版本、引用越界、冲突静默合并、未确认约束升级均被拒绝或降级。
7. `message_seq`、`package_id`、`base_state_version`、`base_package_version` 和 `operation_id` 在跨语言往返中不丢失。
8. Run-scoped Token 不能跨运行、跨包或跨工具；Pi 无法调用写能力。
9. 同一推进链 Manifest 的 `structured_package_input_ref` 一致；L2 装配选择仍由 Python 负责。
10. Python 提交前版本变化返回 `stale`，重复操作返回 `duplicate`，Outbox 投影失败不回滚事实。
