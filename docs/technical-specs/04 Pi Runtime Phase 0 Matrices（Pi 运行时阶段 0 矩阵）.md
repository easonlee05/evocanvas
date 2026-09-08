# Pi Runtime Phase 0 Matrices（Pi 运行时阶段 0 矩阵）

> 文档状态：`现行目标迁移矩阵`
> 目标：`从单次 Pi 调用适配迁移到长期 Primary Pi Session`
> 当前实现状态：`尚未通过阶段 0 出口`

## 1. 权威记录矩阵

| 内容 | 目标权威记录 | 可重建副本 | 禁止的平行记录 |
| --- | --- | --- | --- |
| 用户 / Assistant / Tool 过程 | Pi Session Entry | 压缩摘要、消息 UI | Python 消息历史副本 |
| Pi 技术运行 | Pi Technical Trace / Session | 诊断索引 | 产品侧 Chat / Judgement / Convergence Run |
| 当前稳定业务状态 | 完整不可变工作包 Revision | Context Snapshot、Canvas、交接渲染 | 独立状态账本、Canvas 业务副本 |
| 用户确认 | Revision 内 Confirmation Record | 确认 UI | 仅按对象 ID 的确认布尔值 |
| 下游默认交接 | latest confirmed handoff Revision | 渲染缓存 | 独立交接正文 |
| 外部效果 | 外部回执与幂等查询 | 产品提示 | Assistant 自然语言 |

## 2. Pi 实现基线矩阵

| 项目 | 目标 | 当前实现 | 阶段 0 动作 |
| --- | --- | --- | --- |
| Pi 依赖族 | 所有运行时 Pi 包统一 `0.85.1` | agent-core / ai `0.84.1`，telemetry override `0.84.2` | 统一升级并验证依赖树无混装 |
| Session Backend | Pi 官方 SQLite Backend | 尚未作为 Workspace 长期 Session Store 接入 | 接入官方 Backend |
| 存储单元 | 一个 Session 一个 SQLite 文件 | 旧运行存储与单次请求 | 定义目录、命名、备份与恢复 |
| Writer | 同一 Session 一个宿主独占写者 | 尚无目标式 Session 锁 | 加宿主锁和请求路由 |
| Lane | `main` | 单次请求执行 | 接入原生 Main Lane 与队列 |

## 3. Workspace–Session 矩阵

| 场景 | 目标行为 | 阻断条件 |
| --- | --- | --- |
| 只打开空 Workspace | 不创建 Session；只读 current Revision | 不允许以页面打开制造空历史 |
| 第一条真实消息 | `binding` 预留 Session ID，持久化首条 Entry 后发布 `ready` | 创建任一侧失败不暴露半绑定 |
| 首条消息重试 | 以 `submission_id + content_hash` 返回原 `entry_id` | 同 ID 不同哈希必须冲突 |
| 再次打开 | 恢复同一 Session main lane | 不创建伪装接续的新 Session |
| 用户直接编辑 | 通过统一提交器创建 Revision，不唤起 Pi | Workspace / actor / base Revision 缺失 |
| Session 不可用 | 工作包只读，稳定写入关闭 | 不用聊天摘要或新 Session 替代 |
| 工作包不可用 | Session 可普通对话，稳定写入和交接关闭 | 不用缓存 Canvas 冒充 current Revision |
| close | 释放 Agent 句柄和宿主锁 | 不改变 Binding / Entry / Revision |
| archive | 保留原 Session 和来源解析 | 恢复时仍打开原 Session |
| replace | 新 Session 保留前任和 Entry 映射 | 只用于不可恢复或格式迁移 |
| delete | 协调 Session、工作包、来源和投影 | `partial / retention_held` 不得报成功 |

## 4. 身份矩阵

| 身份 | 生成方 | 稳定用途 | 禁止用途 |
| --- | --- | --- | --- |
| `submission_id` | 客户端 | User Submission 网络重试 | 来源、业务操作、工具调用 |
| `content_hash` | 服务端复算 | 约束同一 Submission 内容 | 单独作为对象身份 |
| `entry_id` | Pi Session | 原始过程和内部来源引用 | 请求幂等、业务操作 |
| `operation_id` | 提交调用方 / 提交器 | 单个语义操作审计与去重 | Pi 技术调用 |
| `invocation_id` / `tool_call_id` | Pi Runtime | 工具调用 Trace | 稳定业务身份 |
| `idempotency_key` | 副作用调用方 | 整次请求与请求哈希去重 | 跨不同动作复用 |

## 5. Pi 资源矩阵

| 资源 | 目标 API 语义 | 版本 / 失败 |
| --- | --- | --- |
| System Instructions | 新 Turn 固定已发布 bundle | 缺失时关闭稳定写入 |
| Skills | Pi 原生加载、发现和按需读取 | 记录实际 Skill 版本；解析失败不声称已使用 |
| `transformContext` | 每次模型调用前读取 current Revision | 失败保留原 User Entry 并禁写 |
| Tools | Runtime 注入 Tool Context | 模型不能伪造身份与权限 |
| Hooks | Context、before/after tool、telemetry | 只做确定性门禁和观测，不做语义路由 |
| Session Backend | 持久 Entry、分支、恢复 | 原 Entry 不被压缩覆盖 |

## 6. 工具、权限与恢复矩阵

| 工具类别 | 示例 | 确认 | `replay` | 幂等 / 并发 |
| --- | --- | --- | --- | --- |
| 只读 | object / revision / source / entry read | 有读取权限即可 | `safe` | 不改变业务状态 |
| 工作包提交 | `workspace.commit` | Pi 推断需内容与范围确认；直接编辑确认自身变化 | `safe`，但必须先查原结果 | `base_revision_id` + 幂等键 |
| 投影 | Canvas rebuild | 诊断或系统能力 | `safe` | `projection_id` 去重，从 Revision 重建 |
| 交接确认 | `confirm_handoff` operation | 交接范围与风险确认 | `safe`，但必须先查 Revision | 目标 Revision 必须仍有效 |
| 外部副作用 | publish / send / create external item | 动作级明确授权 | 默认 `never` | 独立幂等键；未知结果先查询 |
| Workspace 删除 | coordinated delete | 高风险目标确认 | `safe`，仅按原删除进度续作 | 部分失败有恢复记录 |

执行结果始终另记为 `success / failed / unknown`。`unknown` 不等于允许重放；工具缺失 replay 声明时按 `never`。

## 7. 稳定提交矩阵

| 检查顺序 | 输入 | 失败结果 |
| --- | --- | --- |
| 身份与能力 | Runtime Tool Context | `auth.*`，不改变状态 |
| 基础版本 | `base_revision_id` | `workspace.stale_revision` |
| Schema | operations + `operation_id` | 字段路径和稳定 code |
| 来源 | source refs | 保持未验证或阻断依赖事实 |
| 确认 | Entry refs + content / scope hash | `workspace.confirmation_*` |
| 类型化状态和关系 | current snapshot + operations | 非法转换 / 悬空引用 / 依赖环 |
| 幂等 | key + canonical request hash | 返回原结果或冲突 |
| 发布 | complete snapshot | 原子更新 current 指针 |
| 后续 | dependency / handoff impact + Outbox | 与 Revision 同提交或可恢复事件 |

## 8. 失败与恢复矩阵

| 失败 | 工作包是否改变 | 安全恢复 |
| --- | --- | --- |
| 模型 / Provider 失败 | 只取决于此前工具是否成功 | 从 Session 重试，先查工具结果 |
| 用户取消 | 已成功工具不撤销 | 停止后续步骤并显示真实结果 |
| Session 锁冲突 | 否 | 路由持锁宿主或稍后重试 |
| Binding 中途崩溃 | 否或首 Entry 已持久化 | 复用预留 Session ID 完成或标记 unavailable |
| 提交版本冲突 | 否 | 读 Diff，重做受影响确认 |
| 提交响应丢失 | 未知 | 按幂等键和 current Revision 查询 |
| Canvas 渲染失败 | Revision 已改变 | 保留旧投影并重建 |
| 外部调用超时 | 未知 | `replay=never`，查询外部回执 |
| Trace 审计不可用 | 视动作风险 | 高风险写入和副作用在执行前拒绝 |
| 删除部分失败 | 部分目标已删除 | 返回 `partial` 与残留清单，续作同一操作 |
| 合规保留 | 否 | 返回 `retention_held`，不伪报成功 |

## 9. 当前实现迁移矩阵

| 当前资产 | 当前语义 | 目标处理 |
| --- | --- | --- |
| `pi-runtime/src/runtime/executor.ts` | 每请求创建低层 Agent | 迁移到持久 Pi Session / Harness；保留 Provider 适配能力 |
| `pi-runtime/src/server.ts` | chat / judgement / convergence 端点 | 迁移消费者后退役；新主链使用 Session 操作与事件 |
| `app/canvas/pi_kernel.py` | Python 组装上下文并调度多种运行 | 停止新依赖；领域能力转为 Pi Tools / Hooks / Renderer |
| `app/canvas/product_kernel.py` | 外部编排和提案提交 | 拆除 Agent 编排；保留可复用确定性提交能力 |
| `app/canvas/agent_execution/contracts.py` | 旧跨进程 DTO | 数据与消费者迁移后退役 |
| `app/canvas/tool_gateway.py` | 按旧运行类型授权 | 改为按 Tool Context、主体、能力和 side-effect class 授权 |
| `app/canvas/domain/runtime_records.py` | 产品侧运行记录 | 停止新写入；迁移为 Trace / Revision 审计或只读归档 |
| `app/canvas/domain/ledger.py` | 旧追加状态记录 | 迁移到 Revision 后停止新写入并退役 |
| Canvas 现有投影代码 | 页面状态与领域状态混合风险 | 只消费 Revision，保留可复用 Renderer |

## 10. 数据迁移与删除 Preflight

迁移一个 Workspace：短暂停写、导出旧消息、导入预留 Session、校验数量/顺序/角色/附件/哈希、原子切换 Binding、恢复写入。禁止长期双写。

删除旧字段、存储或接口前必须证明：

1. 已盘点全部读写消费者；
2. Session Entry 与来源引用均可解析；
3. 旧消息及运行记录已迁移或明确无需保留，且有内容哈希；
4. 旧状态数据已映射到 Revision，且有校验和；
5. 新主链至少一次端到端成功；
6. 切换前、切换后无新写入、切换后已有新写入三条回退边界均已演练；
7. 删除不会影响现有用户 Workspace；
8. 旧路径不存在新写入者。

## 11. 阶段 0 出口

只有以下全部有证据时才能进入实现迁移：

- Harness 十二项 L3 已冻结；
- 主 PRD 与技术架构已同步；
- 当前写入、读取、数据和消费者清单完成；
- Pi `0.85.1` 依赖族、Session Backend、宿主锁与恢复合同明确；
- Session、身份、Tool Context、Commit、Revision、Projection 与删除合同明确；
- 迁移、回退和删除硬门明确，且不使用长期双写；
- 不再需要新的产品架构选择。
