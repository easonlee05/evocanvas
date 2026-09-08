# Pi Runtime Contract（Pi 运行时接口契约）

> 文档状态：`与 Harness L3 对齐的现行 Pi 集成合同`
> 目标实现归属：`Pi Agent Core + EvoCanvas 产品能力`
> 当前实现状态：`目标合同已定；代码与数据迁移未完成`
> 机器合同：[`schemas/pi-runtime/v1-contracts.json`](./schemas/pi-runtime/v1-contracts.json)

## 1. 控制目标

EvoCanvas 将 Pi 作为唯一 Agent 核心，复用其 Session、Agent Loop、Skills、Context、Tools、Lifecycle 和 Trace。EvoCanvas 只安装产品指令、能力、确定性治理和 Canvas / Handoff Renderer，不在 Pi 外再包装一套 Agent Runtime。

## 2. 依赖与存储基线

首版目标基线固定为：

```text
Pi dependency family: 0.85.1
Session backend: Pi official SQLite backend
Storage unit: one Primary Session per SQLite file
Writer model: one exclusive host writer per Session file
Lane: main
```

约束：

1. `@earendil-works/pi-agent-core`、`@earendil-works/pi-ai` 及实际进入运行路径的 Pi 同族包必须统一为 `0.85.1`，不得混装 `0.84.x / 0.85.x`。
2. 锁由 EvoCanvas 宿主管理，覆盖 Session 打开、恢复、Entry 持久化、工具恢复和压缩；SQLite 不能被当作多宿主写入仲裁器。
3. 未持有锁的请求必须路由到持锁宿主或返回 `runtime.session_locked`，不得打开第二个可写 Session。
4. 当前仓库仍使用 Pi `0.84.1`，这是明确实现缺口，不改变本合同。

## 3. 目标集成边界

```text
EvoCanvas Workspace Host
  -> 接收并去重真实 User Submission
  -> 创建或恢复 Primary Pi Session
  -> 注册 System Instructions / Skills / transformContext / Tools / Hooks
  -> 将原始 User Message 提交给 Session main lane
  -> 订阅 Pi Entry / Tool / Turn / Trace 事件
  -> workspace.commit 创建不可变 Revision
  -> Canvas / Handoff 从 Revision 派生
```

Canvas API 只负责身份、Workspace–Session 绑定、入口幂等和事件转发；不决定 Pi 下一步该回答、追问、读 Skill 还是调用工具。

## 4. Workspace–Session Binding

### 4.1 创建时机

空 Workspace 可以没有 Session。仅打开页面、读取工作包、恢复 Canvas 或查看交接物都不得创建空 Session。第一条真实用户消息到达时才创建 Primary Session。

### 4.2 绑定记录

```text
workspace_id
primary_session_id
main_lane: main
status: binding | ready | unavailable | archived
pi_session_format_version
session_file_ref
created_at
last_opened_at
predecessor_session_id?
unavailable_reason?
```

### 4.3 首条消息原子可见

Session Store 与 Workspace Binding Store 不要求跨库分布式事务，但必须实现等价的原子可见性：

1. 以 `workspace_id + submission_id + content_hash` 取得创建权，预留唯一 `primary_session_id`，Binding 写为 `binding`。
2. 用预留 ID 创建单 Session SQLite 文件并持久化首条 User Entry。
3. 校验 Entry 内容哈希后将 Binding 发布为 `ready`，返回稳定 `entry_id`。
4. 同一 Submission 的所有重试复用预留 ID；调用者在 `ready` 前不能向该 Session 继续写入。

崩溃恢复：文件与首条 Entry 已存在且哈希匹配则完成发布；文件未创建则以同一 ID 重试；不匹配或无法判定则转 `unavailable`。不得另建 Session 伪装连续历史。

## 5. User Submission 合同

用户入口身份与 Pi Entry 身份分离：

```text
submission_id       # 客户端生成的入口重试身份
content_hash        # 服务端按规范化原始内容复算
workspace_id
actor_id
pi_user_message     # 原始 Pi 支持消息结构，不拼接产品提示
```

结果返回：

```text
status: accepted | duplicate
submission_id
content_hash
session_id
entry_id
binding_status: ready
```

规则：

- 相同 `submission_id + content_hash` 返回原 `session_id + entry_id`。
- 相同 `submission_id` 携带不同哈希返回 `runtime.submission_conflict`。
- `submission_id` 不得作为来源 ID、业务操作 ID 或工具调用 ID。
- 当前 User Entry 不拼接工作包摘要、阶段、路由结果、输出 JSON 要求、工具权限说明或伪角色前缀。

## 6. Pi 资源注册

一个 Workspace 的 Pi 实例至少注册：

```text
systemInstructions: instruction bundle + version
skills: published Skill resources + versions
transformContext: WorkspaceContextProjector
tools: read tools + workspace.commit + projection/diagnostic tools + authorized external tools
toolContext: runtime-injected identity and workspace scope
hooks: context + before/after tool + telemetry
session: durable Primary Pi Session
```

资源版本在新 Turn 开始时固定；同一 Tool Loop 内不得静默热切换。

## 7. transformContext 合同

输入由 Pi 提供当前消息、Session / Lane 和 Tool Context。EvoCanvas 投影器只读 current Revision，返回：

```text
original Pi messages
+ temporary Workspace Context Snapshot
+ write_capability status
```

快照不写入 Session，不复制来源正文，不生成独立 Context ID。工作包不可读时保留原消息并关闭稳定写入；不得用旧 Canvas 或缓存冒充 current Revision。

## 8. 身份分层

| 身份 | 权威用途 |
| --- | --- |
| `submission_id` | User Submission 网络重试去重 |
| `entry_id` | Pi Session 中持久 User / Assistant / Tool Entry 与来源追溯 |
| `operation_id` | `workspace.commit` 内单个稳定语义操作的审计和去重 |
| `invocation_id` / Pi `tool_call_id` | 一次 Pi 工具调用的技术身份 |
| `idempotency_key` | 一次有副作用工具请求与规范化请求哈希的去重 |

这些 ID 可在 Trace 中关联，但不得互相复用。

Tool Context 由 Runtime 注入，模型不得声明：

```text
workspace_id
session_id
turn_id
entry_id
invocation_id
tool_call_id
actor_id
capabilities[]
current_revision_id
instruction_bundle_version
active_skill_versions[]
abort_signal
```

## 9. 工具合同与恢复

每个工具必须声明 `side_effect_class`、确认要求、幂等行为、超时行为和：

```text
replay: safe | never
```

- `safe`：纯读取，或具备稳定幂等查询且重复执行无新增效果。恢复时仍须先查询原结果和请求哈希。
- `never`：外部不可逆动作、无可靠幂等查询的动作或重复会新增效果的动作。结果未知时不得自动重放。
- 工具未声明、版本不匹配或策略不可读时一律按 `never`。

执行结果独立表示为 `success | failed | unknown`。`unknown` 不是第三种 replay 策略，也不授予重试许可。

`workspace.commit` 接受：

```text
base_revision_id
idempotency_key
operations[]: operation_id + operation_type + payload
confirmation_refs[]
change_summary
```

它只接受类型化语义操作，不允许整包自由覆写。成功返回 Commit、前后 Revision、变化对象、复核对象、交接影响和投影入队结果。

外部副作用工具独立校验动作级授权、目标、关键参数、幂等和实际回执；工作包或交接确认不能代替外部授权。

## 10. Pi 事件与产品消费

| Pi 事件 | 产品用途 |
| --- | --- |
| User / Assistant Entry persisted | 更新消息界面 |
| message delta | 流式显示，不作为最终事实 |
| Tool Call start / end | 显示执行状态、关联诊断 |
| Turn completed / failed / cancelled | 更新本轮技术状态 |
| Compaction / branch event | 诊断和恢复 |
| Usage / telemetry | 成本与评估 |

稳定业务变化只依据 `workspace.commit` Tool Result 和 Revision；不能从 Assistant 文本或 Turn completed 推断。

## 11. 并发、取消和恢复

- Pi Main Lane 管理单一主动 Tool Loop 和 Steering / Follow-up 队列。
- 工作包并发由 `base_revision_id` 管理，不依赖 Lane 空闲。
- 取消传播给模型和可取消工具；已成功工具效果不自动撤销。
- 进程重启从 Pi Session 恢复技术状态，从 current Revision 恢复业务状态。
- 提交或外部结果未知时按幂等键查询；只有 `replay=safe` 且核对通过时才自动恢复调用。

## 12. close、archive、换代与 delete

- `close`：结束 Agent 句柄并释放宿主锁，不改变 Binding、Session Entry 或 Revision。
- `archive`：将 Workspace 与 Binding 标记归档，保留原 Session 和来源可解析性；恢复时仍打开原 Session。
- `replace`：仅用于原 Session 无法继续或格式迁移；新 Session 记录 `predecessor_session_id` 和 Entry 映射，旧 Session 保留只读。
- `delete`：以独立幂等键协调删除 Session、工作包、来源和投影，终态只能是：
  - `deleted`：全部目标已删除；
  - `partial`：有明确残留与可重试步骤；
  - `retention_held`：保留策略阻止物理删除。

`partial / retention_held` 均不得显示为删除成功。

## 13. 旧消息迁移与回退边界

迁移以 Workspace 为单位：

```text
短暂停止该 Workspace 写入
-> 导出旧消息和来源映射
-> 导入预留的新 Primary Session
-> 校验数量、顺序、角色、附件引用和内容哈希
-> 原子切换 Binding
-> 恢复写入
```

禁止长期双写。回退边界：

1. Binding 切换前：可以放弃新 Session，恢复旧路径写入。
2. 切换后、尚无新 Entry / Revision：仅在完整校验通过时允许原子切回。
3. 切换后已产生新 Entry 或 Revision：旧路径保持只读；只能修复前进或执行下一次受控迁移，不得回到旧路径继续写。

## 14. 失败合同

| 原因码 | 权威状态 | 恢复 |
| --- | --- | --- |
| `runtime.submission_conflict` | 原 Entry 不变 | 生成新 Submission 或修复客户端 |
| `runtime.session_locked` | Session 不变 | 路由持锁宿主或稍后重试 |
| `runtime.session_unavailable` | Binding 不可写 | 恢复原 Session 或受控换代 |
| `instruction.bundle_unavailable` | 本轮无可信指令 | 关闭稳定写入，普通对话按风险降级 |
| `context.workspace_unavailable` | current Revision 不可验证 | 保留 Session，关闭写入 |
| `workspace.stale_revision` | 工作包未改变 | 读取 Diff 并重新确认 |
| `workspace.commit_unknown` | 结果未知 | 按幂等键查询 |
| `external.effect_unknown` | 外部效果未知 | 停止自动重放，核对回执 |
| `projection.render_failed` | Revision 有效、Canvas 落后 | 从 Revision 重建 |
| `lifecycle.delete_partial` | 存在未删除目标 | 显示残留并继续同一删除操作 |
| `lifecycle.retention_held` | 保留目标仍存在 | 显示保留原因，不伪报成功 |

## 15. 合同验收

1. 空 Workspace 反复打开不创建 Session；第一条消息重试只产生一个 Session 和一个 User Entry。
2. 同一 Workspace 重启后恢复同一 Session、main lane 和 Entry 历史。
3. Pi 能在一个 Tool Loop 中读取 Skill、来源、确认依据并提交。
4. `transformContext` 在提交前后分别看到正确 current Revision。
5. 用户直接编辑和 Pi 调用产生相同 Commit 语义。
6. `submission_id / entry_id / operation_id / invocation_id` 分责且可追溯。
7. `replay=never` 的未知工具效果不会在恢复时重复执行。
8. Session 锁竞争不会产生第二个可写 Session。
9. 归档恢复原 Session；删除部分失败或保留挂起均如实返回。
10. 迁移全过程不长期双写，切换后的回退不丢新 Entry 或 Revision。
11. 未确认候选无法进入 Revision 或 Canvas。
12. 关闭旧运行入口后，真实 Workspace 主链仍能完成。
