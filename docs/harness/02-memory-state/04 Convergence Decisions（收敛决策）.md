# Convergence Decisions（收敛决策基线）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Harness 架构决策基线`
> 当前实现状态：`已确认`
> 实现说明：本文件记录 Memory & State 的不可反向推翻决策；详细字段、状态和验收以本组前三份规格为准。

## 1. 控制目标

为实现和后续文档提供一组已冻结的架构约束，防止迁移时重新引入第二套记忆、状态或交接真相源。

## 2. 已确认决策

1. 第一条真实消息后，一个 Workspace 对应一个长期 Primary Pi Session；空 Workspace 不预建 Session。
2. 一个 Workspace 对应一个逻辑统一的结构化工作包。
3. Pi Session 保存原始过程；结构化工作包保存稳定状态。
4. 不建立独立状态账本、Conversation History 或交接正文存储。
5. 每次完整稳定提交创建不可变 Revision，并保存完整快照。
6. 正文变化和治理变化都产生 Revision。
7. 候选和临时方案留在 Session；已固定的未决问题可进入工作包。
8. 同一语义对象跨 Revision 保持 `object_id`；实质替代创建新对象和 `supersedes` 关系。
9. 来源以稳定引用连接对象或关系，不复制正文。
10. 确认绑定具体内容哈希、范围和基础 Revision。
11. current Revision 与最近有效的已确认交接 Revision 分开维护。
12. 用户和 Pi 共用同一受治理提交能力。
13. 用户直接编辑无需转成 Chat，也不自动唤起 Pi。
14. 上游变化只自动标记明确依赖为需复核，不自动重写下游结论。
15. 提交使用基础 Revision、幂等键和原子可见性。
16. Canvas 只显影稳定 Revision。
17. Session 绑定经历 `binding -> ready | unavailable`；崩溃恢复必须完成或回收同一次绑定，不得额外创建伪接续 Session。
18. Session 暂时不可用时，稳定 Revision 仅允许只读；恢复原 Session 或执行受控换代前不得继续稳定写入。
19. Session 关闭只释放运行资源；Workspace 归档保留原 Session 和来源可解析性；Workspace 删除采用协调删除并显式返回 `deleted / partial / retention_held`。
20. 用户入口、Session Entry、稳定操作和工具调用分别使用 `submission_id / entry_id / operation_id / invocation_id`，不得复用一个 ID 混淆重试、来源与副作用。
21. Pi 工具只声明 `replay: safe | never`；执行结果另以 `success | failed | unknown` 表达，`unknown` 不是自动重放许可。
22. Pi Runtime 使用同一版本的 `0.85.1` 依赖族、官方 SQLite Session Backend、一个 Session 一个数据库文件和宿主级独占写锁作为首版实现基线。
23. 旧消息迁移按 Workspace 短暂停写、导入、内容哈希校验和绑定原子切换；不建立长期双写。
24. 切换前可以放弃新 Session 并恢复旧路径；切换后产生新 Entry 或 Revision 后不得回退为旧路径继续写，只能修复前进或再次受控迁移。

## 3. 被排除的方向

- 独立 State Ledger 作为第三事实源。
- 为 Canvas 保存一套业务对象副本。
- 将对话摘要当作当前稳定状态。
- 通过后台模型自动解释每次用户编辑。
- 未确认候选直接生成正式卡片。
- 只按对象 ID 延续确认，不校验内容和范围。
- 新 current Revision 自动取代已确认交接版本。
- Workspace 仅因被打开就创建空 Session。
- Session 不可用时创建无来源连续性的替代 Session。
- 迁移期让旧消息库与 Pi Session 长期双写。
- 用 Tool Call ID 代替用户入口幂等、业务操作或稳定来源 ID。

## 4. 实现约束

任何实现如果需要新增持久对象，必须先证明它不是以下内容的重复副本：Session Entry、工作包 Revision、确认记录、交接指针或 Canvas 投影。若只是索引、缓存、Outbox 或 Trace，必须可从权威记录恢复并明确标注非事实源。

## 5. 变更规则

本基线只能在新证据证明某项决定无法满足 Harness 最高目标时重新打开。重新打开必须记录：受影响决策、反证、替代方案、迁移影响和新的确认；不得通过代码先行或术语替换静默改变。

## 6. 失败与恢复

- 实现方案与本基线冲突：先标记迁移缺口，不以现有代码覆盖目标决策。
- 新证据只影响字段或算法：保持本基线，在 L4 实现规格处理。
- 新证据推翻权威边界：将受影响规范降级并重新收敛，在新决定确认前保留已发布基线。
- 决策记录与主规格不一致：以最新已确认决策修复主规格和链接，保留差异审计。

## 7. 验收场景

1. 架构评审能为每个持久表说明其权威性或可重建性。
2. 任一候选数据路径都不能绕过确认进入稳定 Revision。
3. 用户编辑和 Pi 编辑在并发、幂等和依赖传播上表现一致。
4. Session、工作包或 Canvas 任一层单独故障时，其他两层的事实权限不被改变。
