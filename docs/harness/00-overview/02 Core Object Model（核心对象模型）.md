# Core Object Model（核心对象模型）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`结构化工作包 Schema`
> 当前实现状态：`合同已定，代码待迁移`
> 实现说明：领域对象保存在完整不可变 Revision 中；卡片、交接正文和诊断视图是投影。

## 1. 控制目标

定义最小权威对象、身份和关系，使各 Harness 方法使用同一种稳定语义。

## 2. 根对象

```text
Workspace
  -> Primary Pi Session（第一条真实消息后）
  -> one logical Workspace Artifact（Structured Work Package）
       -> immutable Revisions
            -> Objects
            -> Relations
            -> Confirmations
            -> Handoff State
```

Workspace 绑定过程真相和稳定真相；两者相关联但不互相复制。

`Workspace Artifact` 是结构化工作包的架构名称，不是第三个对象：它就是一个 Workspace 唯一的版本化稳定状态容器；`package_id`、Revision 链、确认和交接指针均属于它。

## 3. 核心对象

| 对象 | 关键身份 | 权威内容 |
| --- | --- | --- |
| Session Entry | `session_id + entry_id` | 用户、Pi、工具原始过程 |
| Work Package | `workspace_id + package_id` | Revision 序列和当前指针 |
| Revision | `revision_id` | 某时点完整稳定对象图和治理元数据 |
| Domain Object | `object_id` | 证据、问题、待澄清、约束、待决策/方案五类独立业务对象 |
| Relation | `relation_id` | supports、contradicts、depends_on 等语义关系 |
| Confirmation | `confirmation_id` | 主体对具体内容、范围和风险的确认 |
| Handoff | `handoff_id` | 某 Revision 的交接状态和确认指针 |
| Projection | `projection_id` | 某 Revision 的 Canvas 渲染检查点 |

Pi Turn、Tool Call、Commit 和外部回执属于运行或审计对象，不是稳定领域对象。

## 4. 五类正式对象与一类交接投影

1. 证据：保留来源陈述、完整性和核验状态。
2. 问题：已经固定的问题定义。
3. 待澄清：已经固定的缺口或歧义。
4. 约束：用户确认的方案边界。
5. 待决策 / 方案承接：正式比较项或已确认决定。
6. 交接物承接卡：指向交接 Revision 和状态的 Canvas 投影，不创建第六份独立业务正文或状态。

Canvas 为前五类稳定对象和交接物投影生成六类正式卡片；候选不创建 `object_id`。

## 5. 身份和版本

- 同一语义对象跨 Revision 保持 ID。
- 实质替代创建新 ID 和 `supersedes` 关系。
- Revision 永不原地修改。
- 确认绑定内容哈希和范围，不只绑定 ID。
- current Revision 与 latest confirmed handoff Revision 分开。
- `submission_id / entry_id / operation_id / invocation_id` 分别标识入口、过程来源、稳定语义操作和工具技术调用，不互相复用。

## 6. 关系和依赖

核心关系：`supports`、`contradicts`、`depends_on`、`clarifies`、`constrains`、`resolves`、`supersedes`、`included_in_handoff`。关系本身可带来源、确认和生命周期；Canvas 连线不是关系权威记录。

## 7. 失败与恢复

对象或关系引用缺失、身份冲突、非法转换、确认范围不匹配或依赖环均阻止整个提交。Projection 可从 Revision 重建；Session Entry 通过稳定引用复水。

## 8. 验收场景

1. 候选方案没有稳定 object ID，也不出现在 Canvas。
2. 实质替代后新旧对象均可追溯。
3. 同一确认不能覆盖修改后内容。
4. Canvas 关系被删除不会删除工作包关系；重新投影恢复。
5. current Revision 和已确认交接指针可独立推进。
