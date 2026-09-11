# Implementation Baseline（实现基线）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi Agent Core + EvoCanvas 产品能力`
> 当前实现状态：`原生实现基线已接入，闭环验证待补齐`
> 实现说明：本基线给出 Orchestration / Lifecycle 的最小原生实现单元；兼容入口不构成目标事实。

## 1. 控制目标

让实现者无需自行发明产品规则，把单次运行与独立收敛入口约束在一个长期 Pi Agent 主链的边界内。

## 2. 必需实现单元

1. **Workspace–Session Binding**：首条真实消息时维护 `workspace_id -> primary_session_id`，实现 `binding / ready / unavailable / archived` 与崩溃恢复。
2. **Instruction / Skill Loader**：向 Pi 注册已发布产品方法，不实现阶段路由。
3. **Context Projector**：在 `transformContext` 中读取 current Revision。
4. **Read Tools**：读取对象、Revision、差异、Session Entry 和来源。
5. **Semantic Commit Tool**：接受受治理操作并原子创建完整 Revision。
6. **Confirmation Resolver**：验证用户确认的主体、内容、范围和时效。
7. **Dependency Checker**：确定性标记复核与交接过时。
8. **Projection Outbox / Renderer**：从 Revision 生成 Canvas。
9. **Trace Correlator**：关联 Session、Tool Call、Commit、Revision 和 Projection。
10. **Session Store / Host Lock**：Pi `0.85.1` 同版本依赖族、官方 SQLite Backend、一个 Session 一个文件、宿主级独占写锁。
11. **Lifecycle Coordinator**：实现 close、archive、受控换代和返回 `deleted / partial / retention_held` 的协调删除。

## 3. 明确不实现

- 产品侧 `run_chat`、`run_judgement`、`run_convergence`。
- Supervisor、阶段机、Skill Router 或收敛租约。
- 平行 Conversation History、Context Manifest 或 State Ledger。
- 后台第二 Agent 自动重写工作包。
- 从 Canvas 反向恢复业务真相。

## 4. 最小接口边界

```text
Pi Agent Core
  receives: User Entry
  uses: Instructions, Skills, transformContext, Tools
  persists: Session Entry and technical Trace

workspace.commit
  receives: runtime identity + base revision + operations(operation_id) + confirmations + idempotency key
  returns: commit result + new revision + dependency and handoff impacts

Canvas Renderer
  receives: workspace id + revision id
  returns: projected revision id + render outcome
```

## 5. 原生闭环补齐顺序

1. 建立首条真实消息触发的 Workspace–Primary Session 绑定、SQLite Session Store、宿主锁和 Revision 读取。
2. 接入 `transformContext` 与只读工具。
3. 让现有稳定写入统一进入语义提交工具。
4. 将用户直接编辑纳入同一提交能力。
5. 移除非主链判断、收敛触发和独立运行状态。
6. 接入依赖传播、交接状态和投影 Outbox。
7. 对历史消息执行停写、导入、哈希校验和按 Workspace 原子切换，不长期双写。
8. 完成 Trace 关联与端到端验收后再删除兼容字段。

兼容期间历史字段只能作为输入，不能继续产生新的目标状态语义。

## 6. 原因码基线

```text
instruction.*     # 指令包与 Skill 制品
context.*         # 上下文装配与复水
runtime.*         # Pi 技术运行
proposal.*        # 尚未进入提交的提案就绪问题
source.*          # 来源完整性与核验
auth.*            # 身份、能力与范围
workspace.*       # Revision、确认、状态、依赖和提交
handoff.*         # 交接确认、暂停与失效
tool.* / external.* # 通用工具和外部副作用
projection.*      # Canvas 投影
trace.*           # 追踪与诊断关联
verification.*    # 确定性验证
eval.*            # 离线评估
```

同一失败条件必须复用拥有该状态的子系统原因码，不能由上层包装器重新命名。例如基础版本过时统一为 `workspace.stale_revision`，权限不足统一为 `auth.capability_denied`。每个原因码必须有稳定机器码、可读消息、是否可重试和权威状态是否改变四项定义。

## 7. 失败与恢复

- Binding 创建中断：复用预留 Session ID 完成，无法核对时转 `unavailable`。
- Session 锁丢失：停止该宿主写入并路由到持锁宿主，不创建第二个可写 Session。
- 工具恢复：只有 `replay=safe` 且幂等核对通过时自动续作；其他情况停在 `unknown`。
- 历史数据校验失败：原子切换前恢复原入口；切换后已有新事实则只允许修复前进或再次受控导入。
- 协调删除失败：返回 `partial` 或 `retention_held` 与残留清单，不伪报成功。

## 8. 完成证据

本模块只有在以下证据齐全时才算实现完成：

- 一个 Workspace 的真实长期 Pi Session 可跨进程恢复；
- 目标链路不再调用非主链独立运行类型；
- 用户和 Pi 编辑经过同一提交器；
- 未确认候选无法进入 Revision；
- current 与 confirmed handoff 双指针按规则工作；
- Canvas 可从 Revision 重建；
- 并发、超时、取消和结果未知场景有测试；
- Trace 能从用户 Entry 追溯到 Revision 和投影；
- `submission_id / entry_id / operation_id / invocation_id` 分责且可关联；
- 工具恢复遵守 `replay: safe | never`，未知外部效果不被自动重放；
- close、archive、换代和协调删除均通过故障注入测试。

## 9. 验收场景

1. 搜索确认生产路径不存在非主链运行类型的主动调用。
2. 真实端到端流程中同一 Pi 完成读取、确认、提交和回复。
3. 提交后投影失败再恢复，无重复 Revision 或语义重跑。
4. 历史客户端兼容请求不能绕过新提交器直接写稳定状态。
5. 兼容开关关闭后，完整回归仍通过。
