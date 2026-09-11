# Technical Baseline（技术落地总览）

> 文档集状态：`Harness L3 的现行技术入口；不包含历史快照`
> 编码门槛：`以主 PRD、Harness L3 和本目录现行规格为目标合同，并在修改前核对当前代码与测试`

## 1. 文档定位

本目录只保存当前仍可作为实现输入的技术规格，不保存历史 L / G / V 方案、过期接口快照或兼容文件名。

权威顺序固定为：

1. `docs/vision/EvoCanvas1.0-PRD.md`：产品边界、用户体验和 1.0 最小闭环；
2. `docs/harness/`：十二项方法的治理规格；
3. `docs/technical-specs/`：将 L3 规则翻译为架构、运行合同、实现矩阵和原生闭环硬门；
4. 当前代码与测试：实现证据，不得反向覆盖目标规则。

发生冲突时先按该顺序修正文档；不能让技术快照成为第二产品真相源。

## 2. 现行规格清单

| 顺序 | 文档 | 唯一职责 |
| --- | --- | --- |
| 00 | 本文 | 权威顺序、阅读入口和实现边界 |
| 01 | [System Architecture（系统总架构）](./01%20System%20Architecture%EF%BC%88%E7%B3%BB%E7%BB%9F%E6%80%BB%E6%9E%B6%E6%9E%84%EF%BC%89.md) | 目标子系统、数据方向和事实源 |
| 02 | [Architecture Traceability（架构可追溯矩阵）](./02%20Architecture%20Traceability%EF%BC%88%E6%9E%B6%E6%9E%84%E5%8F%AF%E8%BF%BD%E6%BA%AF%E7%9F%A9%E9%98%B5%EF%BC%89.md) | PRD、Harness、架构和实现证据的追溯 |
| 03 | [Pi Runtime Contract（Pi 运行时接口契约）](./03%20Pi%20Runtime%20Contract%EF%BC%88Pi%20%E8%BF%90%E8%A1%8C%E6%97%B6%E6%8E%A5%E5%8F%A3%E5%A5%91%E7%BA%A6%EF%BC%89.md) | Session、身份、工具、恢复和生命周期合同 |
| 04 | [Pi Runtime Implementation Matrices（Pi 运行时原生实现矩阵）](./04%20Pi%20Runtime%20Implementation%20Matrices%EF%BC%88Pi%20%E8%BF%90%E8%A1%8C%E6%97%B6%E5%8E%9F%E7%94%9F%E5%AE%9E%E7%8E%B0%E7%9F%A9%E9%98%B5%EF%BC%89.md) | 原生目标与当前实现的逐项对照矩阵 |
| 05 | [Pi Runtime Native Readiness（Pi 运行时原生就绪核对）](./05%20Pi%20Runtime%20Native%20Readiness%EF%BC%88Pi%20%E8%BF%90%E8%A1%8C%E6%97%B6%E5%8E%9F%E7%94%9F%E5%B0%B1%E7%BB%AA%E6%A0%B8%E5%AF%B9%EF%BC%89.md) | 当前证据、历史数据导入、回退与删除硬门 |
| Schema | [Pi Runtime v1 contracts](./schemas/pi-runtime/v1-contracts.json) | 现行机器可读边界与 fixtures |

同一规则只在一个文档中展开：系统边界看 01，追溯看 02，字段和恢复合同看 03，实施对照看 04，当前原生就绪证据与硬门看 05。

## 3. 当前实现判断

当前代码已形成 EvoCanvas 原生主链，兼容入口与完整验证边界如下：

- Pi Runtime 使用统一的 `0.85.1` 依赖族、Session 存储、Revision 存储和工作区 v1 端点；
- TypeScript 主链按 Workspace 绑定 Primary Session，使用 `workspace.propose` 与 `workspace.commit` 驱动稳定 Revision，并从 Revision 生成 Canvas 投影；
- Python Canvas 入口通过 `CanvasService.run_pi_turn` 接入该工作区主链；非主链运行类型被隔离，不参与生产画布主路径；
- Session 恢复、幂等提交、过时 Revision、直接编辑、交接读取和投影重建已有自动化覆盖；真实 Provider、浏览器人工链路和全部 Harness 边界仍需继续验证。

详细证据集中在 05，不在其他技术规格重复维护。

## 4. 实现边界

本目录处理：

- Pi 作为唯一 Agent 核心的集成方式；
- Workspace–Session、Entry、Commit、Revision、Handoff 与 Projection 的权威关系；
- 工具权限、幂等、恢复、生命周期和兼容删除硬门；
- 当前代码如何持续收敛到 Harness L3。

本目录不处理：

- 重新定义 PRD、页面或卡片类型；
- 在 Pi 外新建 Agent Kernel、Supervisor 或阶段路由器；
- 为兼容现有调用方新增长期双写、平行事实源或平行确认流；
- 把尚未被主 PRD / Harness 支撑的新产品规则写成实现事实；
- 把文档已收敛误报为代码或生产链已经完成。

## 5. 首批实现原则

- 空 Workspace 不创建 Session；第一条真实消息才创建并绑定 Primary Session。
- Pi 同族运行依赖统一使用 `0.85.1`，采用官方 SQLite Backend、一个 Session 一个文件和宿主级独占写锁。
- `submission_id / entry_id / operation_id / invocation_id` 分责并可追溯。
- 用户直接编辑与 Pi 编辑共用 `workspace.commit`；未确认候选不进入 Revision 或 Canvas。
- 工具声明 `replay: safe | never`；结果 `unknown` 不自动授予重放权限。
- 历史数据按 Workspace 停写、导入、哈希校验、原子切换，不长期双写。
- close、archive、replace、delete 分责；删除必须如实返回 `deleted / partial / retention_held`。
- 实现完成必须由真实入口、恢复、并发、历史数据导入和端到端测试证明。
