# Projection Signals（显影提示）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Canvas Renderer + 工作区界面`
> 当前实现状态：`合同已定，代码待迁移`
> 实现说明：显影和提示只反映已提交 Revision 及其投影状态，不从对话候选生成正式卡片。

## 1. 控制目标

让用户低打扰地看见稳定结构何时发生变化、当前 Canvas 是否最新，以及哪些对象需要复核或交接已过时。

## 2. 投影输入输出

**输入**：`workspace_id + revision_id + renderer_version`。

**输出**：

```text
projection_id
projected_revision_id
renderer_version
status: pending | rendering | ready | failed
changed_node_ids[]
started_at
finished_at?
failure_code?
```

Renderer 不读取 Pi 候选文本决定业务节点，也不更新工作包状态。

## 3. 用户信号

| 情况 | Canvas | 提示 |
| --- | --- | --- |
| 无稳定提交 | 不变 | 无需提示 |
| Revision 已提交、待投影 | 保留旧投影并标识同步中 | 低打扰状态 |
| 投影成功 | 显示新 Revision | 变化摘要可选 |
| 对象需复核 | 对应稳定对象显示复核标记 | 说明上游变化 |
| 交接暂停或失效 | 交接承接卡显示状态 | 明确不可继续使用 |
| 投影失败 | 保留旧投影并标注落后 | 提供重建动作 |

Toast 只是一种界面提示，不是确认、提交或错误记录。

## 4. 变化摘要

变化摘要由 `previous_projected_revision_id -> target_revision_id` 的确定性差异生成，只描述新增、修改、状态变化和受影响对象。不得由模型自由总结后替代 Revision Diff。

## 5. 失败与恢复

- Outbox 重复：按 `projection_id` 幂等。
- Renderer 失败：记录失败并重建，不重提工作包。
- 新 Revision 追上旧任务：可以跳过中间渲染，但必须保证最终 `projected_revision_id=current_revision_id`，且历史 Revision 可诊断。
- 客户端离线：重新连接时比较指针并获取最新投影。

## 6. 验收场景

1. Pi 只讨论候选时不出现正式卡片或变化 Toast。
2. 提交成功但投影失败时，界面明确显示旧 Revision，不冒充最新。
3. 重复投影事件不会生成重复节点。
4. 上游约束变化后，下游卡片显示复核标记但正文不被改写。
5. 删除投影缓存后，从 current Revision 可重建相同业务节点和关系。
