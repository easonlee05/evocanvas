# Lifecycle（生命周期）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi Session + 结构化工作包 + Canvas 投影`
> 当前实现状态：`原生生命周期已接入，恢复边界待验证`
> 实现说明：技术运行、稳定状态和派生投影分别拥有生命周期，不能互相代替。

## 1. 控制目标

明确各类记录何时创建、何时成为当前状态、何时结束或过时，以及故障后从哪里恢复。

## 2. 生命周期矩阵

| 对象 | 创建 | 当前性 | 结束 / 过时 | 权威恢复源 |
| --- | --- | --- | --- | --- |
| Workspace–Session Binding | 第一条真实用户消息，先写 `binding` | `ready` 指向唯一 Primary Session | `unavailable / archived / deleted` | Binding Store + Pi Session Store |
| Pi Session | Binding 预留 ID 后创建 | `ready` Binding 指向的 Primary Session | close 仅释放资源；archive 保留；受控换代或协调删除 | Pi Session Store |
| Session Entry | 用户、助手或工具事件 | 当前分支可见 | 不修改；可被压缩摘要覆盖模型窗口 | 原 Entry |
| Pi 技术运行 | 新 Prompt / 恢复动作 | Main Lane active operation | completed / cancelled / failed / suspended | Pi Session + Trace |
| 工作包 Revision | 原子稳定提交 | `current_revision_id` | 被后续 Revision 取代当前性，历史不删除 | Revision Store |
| 稳定对象 | 用户固定语义后首次进入 Revision | current Revision 中使用主 PRD 的唯一类型化状态 | 按类型进入已关闭 / 已归档 / 已替代等终态 | 对应 Revision |
| 确认记录 | 对具体内容与范围确认 | 内容哈希和依赖仍匹配 | 不再覆盖新内容，历史保留 | 对应 Revision |
| 交接 | 从 Revision 生成 | 最近有效 confirmed 版本 | suspended / invalidated / superseded | 已确认 Revision |
| Canvas 投影 | 消费 Revision | 标记其 `projected_revision_id` | 新投影替代或缓存删除 | Revision 重建 |

## 3. Revision 发布

新 Revision 只有在完整快照、确定性验证、确认校验和依赖传播全部成功后，才能原子更新 current 指针。创建了内部草稿但未更新指针的记录不得对读者可见，需由恢复任务清理。

## 3.1 Session Binding 发布

仅打开空 Workspace 不创建 Session。第一条真实消息按以下顺序建立绑定：

1. 以 `workspace_id + submission_id + content_hash` 取得创建权并预留 `primary_session_id`，状态为 `binding`；
2. 使用预留 ID 创建单 Session SQLite 文件并持久化首条 User Entry；
3. 校验 Entry 哈希后将 Binding 发布为 `ready`，返回稳定 `entry_id`；
4. 任何重试复用同一 `submission_id` 和预留 Session ID，不创建第二个 Session。

崩溃后若 Session 文件和首条 Entry 已存在则完成发布；尚未创建则以同一预留 ID 重试；内容不匹配或无法判定时转为 `unavailable` 并进入人工恢复。孤立文件只可隔离或回收，不能自动成为另一个 Workspace 的 Session。

## 4. 对象推进

候选不是稳定生命周期状态。对象第一次进入工作包时即应具有明确的信息地位和生命周期状态。对象正文、关系、状态或确认变化均通过新 Revision 表达；历史 Revision 永不原地修改。

## 5. 交接推进

交接 `draft / confirmed / suspended / invalidated / superseded` 的转换及 current 与 latest-confirmed 双指针见 Memory & State 规格。下游只能使用有效的 confirmed 版本。

## 6. 删除与保留

- 业务撤回使用状态而非物理删除历史 Revision。
- Canvas 和快照缓存可物理清除并重建。
- `close` 只结束当前 Agent 句柄、释放 Session 文件锁和运行资源，不改变 Binding、Entry 或 Revision。
- `archive` 将 Binding 与 Workspace 标记为归档，保留原 Session、Entry、Revision 和来源引用；恢复时仍打开原 Session。
- 受控 Session 换代只在原 Session 无法继续使用或格式切换时发生：新 Session 必须记录前任引用和 Entry 映射，原 Entry 仍可解析；不得用换代掩盖普通故障。
- Workspace `delete` 是独立高风险动作，协调处理 Session、工作包、来源和投影，并返回唯一终态：`deleted`（目标均已删除）、`partial`（存在明确残留和可重试步骤）、`retention_held`（因保留策略未物理删除）。
- `partial / retention_held` 均不得向用户显示为删除成功；重复删除请求复用同一幂等键和进度记录。

## 7. 失败与恢复

- current 指针更新前失败：新 Revision 不可见，安全重试同一幂等请求。
- 指针更新后响应失败：按幂等键或 current 指针确认成功。
- 投影落后：比较 `projected_revision_id` 与 `current_revision_id` 后重放。
- 确认依赖变化：更新交接和复核标记，不删除旧确认。
- Session 技术运行无法恢复：稳定 Revision 不受影响；必须先恢复原 Session，或按受控换代规则建立可追溯的新 Session，才能以 current Revision 作为业务状态继续；不得在 `unavailable` 状态下另建伪接续 Session。
- Primary Session 暂时不可用：current Revision 只读；恢复原 Session 或完成受控换代前关闭稳定写入。

## 8. 验收场景

1. 历史 Revision 可重放得到当时完整状态。
2. 工作包新版本发布中途失败，读者只能看到旧完整版本或新完整版本。
3. 已关闭、已归档或已替代对象仍可在历史版本和来源链中审计。
4. Canvas 明确显示所投影的 Revision，落后时不冒充最新。
5. Pi 技术运行失败不会把交接状态改成 failed。
6. 空 Workspace 被反复打开不会产生 Session 文件；第一条消息重试只产生一个 Session 和一个 User Entry。
7. 归档后恢复打开原 Session；删除部分失败时返回残留清单而不是成功。
