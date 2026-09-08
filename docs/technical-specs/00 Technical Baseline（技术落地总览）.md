# Technical Baseline（技术落地总览）

> 文档集状态：`Harness L3 的现行技术入口；不包含历史快照`
> 编码门槛：`以主 PRD、Harness L3 和本目录现行规格为目标合同，并在修改前核对当前代码与测试`

## 1. 文档定位

本目录只保存当前仍可作为实现输入的技术规格，不保存旧 L / G / V 方案、过期接口快照或兼容文件名。

权威顺序固定为：

1. `docs/vision/EvoCanvas1.0-PRD.md`：产品边界、用户体验和 1.0 最小闭环；
2. `docs/harness/`：十二项方法的治理规格；
3. `docs/technical-specs/`：将 L3 规则翻译为架构、运行合同、矩阵和迁移硬门；
4. 当前代码与测试：实现证据，不得反向覆盖目标规则。

发生冲突时先按该顺序修正文档；不能让技术快照成为第二产品真相源。

## 2. 现行规格清单

| 顺序 | 文档 | 唯一职责 |
| --- | --- | --- |
| 00 | 本文 | 权威顺序、阅读入口和实现边界 |
| 01 | [System Architecture（系统总架构）](./01%20System%20Architecture%EF%BC%88%E7%B3%BB%E7%BB%9F%E6%80%BB%E6%9E%B6%E6%9E%84%EF%BC%89.md) | 目标子系统、数据方向和事实源 |
| 02 | [Architecture Traceability（架构可追溯矩阵）](./02%20Architecture%20Traceability%EF%BC%88%E6%9E%B6%E6%9E%84%E5%8F%AF%E8%BF%BD%E6%BA%AF%E7%9F%A9%E9%98%B5%EF%BC%89.md) | PRD、Harness、架构和实现证据的追溯 |
| 03 | [Pi Runtime Contract（Pi 运行时接口契约）](./03%20Pi%20Runtime%20Contract%EF%BC%88Pi%20%E8%BF%90%E8%A1%8C%E6%97%B6%E6%8E%A5%E5%8F%A3%E5%A5%91%E7%BA%A6%EF%BC%89.md) | Session、身份、工具、恢复和生命周期合同 |
| 04 | [Pi Runtime Phase 0 Matrices（Pi 运行时阶段 0 矩阵）](./04%20Pi%20Runtime%20Phase%200%20Matrices%EF%BC%88Pi%20%E8%BF%90%E8%A1%8C%E6%97%B6%E9%98%B6%E6%AE%B5%200%20%E7%9F%A9%E9%98%B5%EF%BC%89.md) | 目标与当前资产的逐项迁移矩阵 |
| 05 | [Pi Runtime Migration Preflight（Pi 运行时迁移前置核对）](./05%20Pi%20Runtime%20Migration%20Preflight%EF%BC%88Pi%20%E8%BF%90%E8%A1%8C%E6%97%B6%E8%BF%81%E7%A7%BB%E5%89%8D%E7%BD%AE%E6%A0%B8%E5%AF%B9%EF%BC%89.md) | 当前证据、数据迁移、回退与删除硬门 |
| Schema | [Pi Runtime v1 contracts](./schemas/pi-runtime/v1-contracts.json) | 现行机器可读边界与 fixtures |

同一规则只在一个文档中展开：系统边界看 01，追溯看 02，字段和恢复合同看 03，实施对照看 04，当前迁移证据与硬门看 05。

## 3. 当前实现判断

当前代码已复用部分 Pi 和 Canvas 通用底座，但尚未形成目标主链：

- Pi 依赖仍为 `0.84.1`，且 telemetry override 为 `0.84.2`；目标是同一 `0.85.1` 依赖族；
- TypeScript 侧仍保留单次运行入口和每请求 Agent；
- Python 侧仍承担外部上下文组装、判断、收敛和产品运行记录；
- Workspace–Primary Session Binding、官方 SQLite Session Backend、宿主独占写锁、统一 `workspace.commit` 和 Revision 投影闭环尚未完成；
- 旧 Schema 已由现行 Session / Tool / Commit / Lifecycle Schema 替换，但业务代码消费者尚未迁移。

详细证据集中在 05，不在其他技术规格重复维护。

## 4. 实现边界

本目录处理：

- Pi 作为唯一 Agent 核心的集成方式；
- Workspace–Session、Entry、Commit、Revision、Handoff 与 Projection 的权威关系；
- 工具权限、幂等、恢复、生命周期和迁移硬门；
- 当前代码资产如何迁移到 Harness L3。

本目录不处理：

- 重新定义 PRD、页面或卡片类型；
- 在 Pi 外新建 Agent Kernel、Supervisor 或阶段路由器；
- 为兼容旧代码新增长期双写、平行事实源或平行确认流；
- 把尚未被主 PRD / Harness 支撑的新产品规则写成实现事实；
- 把文档已收敛误报为代码或生产链已经完成。

## 5. 首批实现原则

- 空 Workspace 不创建 Session；第一条真实消息才创建并绑定 Primary Session。
- Pi 同族运行依赖统一使用 `0.85.1`，采用官方 SQLite Backend、一个 Session 一个文件和宿主级独占写锁。
- `submission_id / entry_id / operation_id / invocation_id` 分责并可追溯。
- 用户直接编辑与 Pi 编辑共用 `workspace.commit`；未确认候选不进入 Revision 或 Canvas。
- 工具声明 `replay: safe | never`；结果 `unknown` 不自动授予重放权限。
- 迁移按 Workspace 停写、导入、哈希校验、原子切换，不长期双写。
- close、archive、replace、delete 分责；删除必须如实返回 `deleted / partial / retention_held`。
- 实现完成必须由真实入口、恢复、并发、迁移和端到端测试证明。
