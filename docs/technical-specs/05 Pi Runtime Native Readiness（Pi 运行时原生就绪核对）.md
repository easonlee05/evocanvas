# Pi Runtime Native Readiness（Pi 运行时原生就绪核对）

> 文档状态：`当前原生实现证据与兼容硬门`
> 核对日期：`2026-09-08`
> 目标架构：`空 Workspace 可无 Session；首条真实消息后，一个 Workspace 绑定一个长期 Primary Pi Session`
> 当前结论：`原生合同已封口；主链已接入，完整生产证据待补齐`

## 1. 核对原则

本文件只记录当前代码事实、数据风险和原生就绪条件。目标产品规则以主 PRD 和 Harness L3 为准；兼容入口不能反向改变原生架构。

工作区已有修改均视为用户资产。进行原生实现核对前必须再次核对 `git status --short`，不得覆盖、回退或顺带格式化无关文件。

## 2. 当前实现证据

### 2.1 Pi 依赖

`pi-runtime/package.json` 当前使用：

```text
@earendil-works/pi-agent-core 0.85.1
@earendil-works/pi-ai 0.85.1
@earendil-works/pi-session-backend-sqlite-node 0.85.1
@earendil-works/pi-telemetry 0.85.1
```

依赖族已统一为 `0.85.1`；仍需以 lockfile 依赖树、构建、测试和真实 Session 恢复证据持续确认。

### 2.2 TypeScript Pi Runtime

当前可观察事实：

- `WorkspaceSessionStore` 按 Workspace 绑定 Primary Session，并以 SQLite Session 文件保存 Entry；
- `WorkspaceRevisionStore` 维护完整不可变 Revision、current / confirmed handoff 指针和幂等提交；
- `pi-runtime/src/server.ts` 已提供 binding、submission、turn、commit、projection、revision 和 lifecycle 端点；
- chat / judgement / convergence 端点仍保留为兼容边界，Workspace 主链不依赖它们；
- 相邻测试覆盖首条消息幂等、Session 重启恢复、候选确认、直接编辑、过时版本、投影重建和跨语言调用。

### 2.3 Python Canvas / Agent 路径

当前可观察事实：

- `app/canvas/pi_kernel.py` 的生产入口通过 Primary Pi Session 和 Workspace Commit 驱动画布与投影；
- `app/canvas/product_kernel.py`、辅助运行合同和运行记录仍作为隔离边界存在；
- `app/canvas/tool_gateway.py` 继续承担工具身份、能力和副作用授权；
- `app/api/server.py` 已将 Canvas 请求接入 Workspace Runtime，并保留既有兼容接口；
- 真实 Provider、浏览器人工链路、跨宿主路由和全部 Harness 边界仍需在目标环境补证。

## 3. 目标与当前差距

| 能力 | 原生目标 | 当前 | 原生动作 |
| --- | --- | --- | --- |
| Workspace Session | 首条真实消息创建长期 Primary Session | Workspace Session Store 已接入 | 补齐真实环境恢复证据 |
| Session Store | SQLite；一 Session 一文件；宿主独占写 | Session 文件、锁和 Binding 已接入 | 补齐跨宿主边界验证 |
| Pi 依赖 | 全族 `0.85.1` | 已统一为 `0.85.1` | 持续验证 lockfile 与构建 |
| User Submission | `submission_id + content_hash` 去重 | Submission receipt 已接入 | 补齐入口重试与异常恢复证据 |
| Skills | Pi 原生发现并自主使用 | 产品指令与工具链已接入 | 补齐资源版本 Trace |
| Context | `transformContext` 读 current Revision | Workspace Context Projector 已接入 | 补齐降级与边界验证 |
| Runtime | 一个正常 Tool Loop | Workspace Agent Loop 已接入 | 继续隔离兼容运行类型 |
| Stable Write | 用户和 Pi 共用 `workspace.commit` | 统一提交器已接入 | 补齐直接编辑与确认一致性证据 |
| Tool Recovery | `replay=safe|never` + `success|failed|unknown` | 工具恢复合同已接入 | 补齐未知结果与重启演练 |
| State | 完整不可变 Revision + 类型化对象状态 | Revision Store 已接入 | 补齐历史数据导入校验 |
| Canvas | 只投影 Revision | Projection Renderer 已接入 | 补齐投影失败重建证据 |
| Handoff | current / latest confirmed 双指针 | Handoff 指针与读取已接入 | 补齐过时与失效边界 |
| Lifecycle | close / archive / replace / coordinated delete | 生命周期端点与状态合同已接入 | 补齐部分失败与保留策略 |
| Trace | Entry -> Invocation -> Operation -> Revision -> Projection | 关联字段已接入 | 补齐真实链路诊断视图 |

## 4. 原生闭环必须完成的数据盘点

### 4.1 读写消费者

必须列出以下对象的全部写入、读取、查询和删除入口：

- Conversation / message / Session 数据；
- 兼容请求快照和运行 DTO；
- Judgement / Convergence / Commit 运行记录；
- Structured Package / Snapshot / Handoff；
- Ledger / confirmation / watermark；
- Card、relation、projection 和 Todo；
- Tool Gateway / Outbox / Trace。

### 4.2 真实数据

需要证明：

- 本地或生产样本是否存在兼容运行记录；
- 历史 `conversation_id` 能否稳定映射到 Primary Session；
- 工作包历史能否构造完整 Revision；
- 来源引用是否依赖历史消息序号或即将删除的文件路径；
- 交接确认和状态是否能无损映射；
- Canvas 中是否存在无法回指稳定对象的卡片。

未完成盘点前不得删除字段、存储或 API。

## 5. 按 Workspace 执行历史数据导入

一个 Workspace 的导入固定为：

1. **预检**：验证消息、来源、工作包和交接均可映射。
2. **短暂停写**：只冻结该 Workspace 的历史消息与兼容写入入口，读取保持可用。
3. **预留 Binding**：创建 `binding` 记录和唯一 `primary_session_id`。
4. **导入 Session**：按原顺序导入 User / Assistant / Tool 过程与附件引用。
5. **导入 Revision**：将当前稳定状态转换为完整不可变 Revision。
6. **校验**：核对数量、角色、顺序、来源映射、内容哈希、确认和交接指针。
7. **原子切换**：一次更新 Binding 与新权威指针，兼容入口同时转只读。
8. **恢复写入**：新 User Submission 和稳定提交只进入原生主链。
9. **观察与退役**：观察期通过后关闭兼容写入者，最后按删除硬门处理历史存储。

导入期间不长期双写。影子校验只能读取同一冻结输入做离线比较，不得让两条路径同时产生可写事实。

## 6. 回退边界

| 时点 | 允许动作 | 禁止动作 |
| --- | --- | --- |
| Binding 切换前 | 放弃新 Session，解除兼容入口停写 | 发布半绑定或半导入数据 |
| 切换后且尚无新 Entry / Revision | 完整校验后原子恢复原入口 | 两边同时恢复写入 |
| 切换后已产生新 Entry 或 Revision | 修复前进，或再次执行受控导入 | 回到兼容入口继续写、丢弃新事实 |
| 已产生外部副作用 | 保留回执并按副作用恢复合同处理 | 因代码回退伪装动作未发生 |

每次回退或修复前进都记录 Workspace、导入批次、哈希、切换点、已产生的新事实和操作者。

## 7. 删除硬门

删除已退出主链的 API、Schema、存储或兼容字段前，必须全部满足：

1. `rg`、测试和运行时观测证明无新写入者；
2. 全部读取者已切换到原生主链或有明确只读兼容层；
3. 历史数据导入数量、内容哈希和抽样语义核对通过；
4. 新主链端到端覆盖首条消息、普通对话、确认提交、直接编辑、交接和投影；
5. 并发、锁、取消、超时、未知结果、归档、换代、删除和重建测试通过；
6. 观察期内无关键回归；
7. 三段回退边界均演练；
8. 删除得到独立执行授权。

## 8. 文档封口与实现出口分离

### 文档合同已满足

- 主 PRD、模块文档、Harness 与现行 Technical Specs 使用同一产品与架构边界；
- 目标 Session、身份、Context、Tool、Commit、Revision、Handoff、Projection、Lifecycle 和历史数据导入规则已明确；
- 机器可读 Schema 不再新增非主链运行类型；
- 历史技术快照已从现行规格目录移除。

### 实现仍未满足

- 全量真实数据和消费者盘点；
- Pi `0.85.1` 依赖族、官方 Session Backend 与恢复证据；
- Workspace–Primary Session 的真实环境恢复证据；
- `workspace.commit` 与完整 Revision 的一致性证据；
- 历史数据导入、观察与回退演练；
- 生产入口端到端证据；
- 非主链写入路径停止写入并取得删除授权。

因此可以依据文档继续验证和完善原生实现，但不能仅凭文档声称完整生产闭环已经完成。
