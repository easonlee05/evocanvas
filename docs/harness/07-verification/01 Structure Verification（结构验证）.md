# Structure Verification（结构验证）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`结构化工作包 Schema 与提交器`
> 当前实现状态：`原生结构验证已接入，边界场景待验证`
> 实现说明：在新 Revision 可见前验证完整快照和所有语义操作。

## 1. 控制目标

保证工作包的对象、关系、状态、确认和交接指针始终可以被实现、读取和重建，不产生悬空或半有效状态。

## 2. 提交前检查

1. `workspace_id / package_id / base_revision_id` 匹配。
2. 幂等键格式有效且未与不同请求复用。
3. 所有 operation 符合对应 Schema。
4. `object_id / relation_id / confirmation_id` 唯一。
5. 被引用对象存在于基础版本或同一原子提交中。
6. 对象类型、信息地位和生命周期转换合法。
7. 关系类型允许且无禁止的依赖环。
8. 确认内容哈希与目标内容、范围和 Revision 匹配。
9. 交接指针指向存在且状态允许的 Revision。
10. 依赖传播结果可完整应用。

## 3. 提交后检查

生成完整快照后验证：快照 Schema、父版本、对象和关系计数、引用完整性、内容哈希、current 指针原子性。只有全部通过才发布 current 指针。

## 4. 投影结构验证

Renderer 输出必须带 `projected_revision_id`，且业务节点和关系可映射到该 Revision 的稳定对象。布局节点可以多于业务对象，但必须明确为非事实 UI 元素。

## 5. 失败与恢复

| 原因码 | 处理 |
| --- | --- |
| `verification.schema_invalid` | 拒绝提交并返回字段路径 |
| `verification.reference_missing` | 拒绝包含悬空引用的原子组 |
| `verification.invalid_transition` | 返回对象和前后状态 |
| `verification.dependency_cycle` | 返回最小环路径 |
| `verification.snapshot_corrupt` | 不发布指针，隔离故障快照 |
| `verification.projection_mismatch` | 标记投影 failed 并重建 |

## 6. 验收场景

1. 同一提交创建对象和指向它的关系可以通过。
2. 指向不存在对象的关系导致整个提交失败。
3. 确认哈希不匹配时即使对象 ID 相同也失败。
4. current 指针更新前存储故障，读者仍只看到旧完整 Revision。
5. Canvas 多出无来源正式卡片时投影验证失败。
