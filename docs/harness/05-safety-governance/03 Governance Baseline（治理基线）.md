# Governance Baseline（治理基线）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`EvoCanvas 领域 Schema、Hooks 与提交器`
> 当前实现状态：`原生治理基线已接入，完整验证待补齐`
> 实现说明：本文件汇总实现时不可缺少的治理数据和门禁顺序。

## 1. 控制目标

提供统一最小基线，避免对象、交接和外部工具各自发明不同的确认、权限和审计语义。

## 2. 必需治理数据

```text
actor: actor_id + capability set
source: source_ref + integrity status + verification status
object: object_id + type + lifecycle status + information status
confirmation: actor + revision + scope + content hashes + risks + time
commit: base revision + operations + idempotency key + policy versions
handoff: target revision + status + confirmation + invalidation causes
```

## 3. 门禁顺序

```text
身份与能力
-> 基础 Revision
-> 输入 Schema
-> 来源与引用完整性
-> 确认内容和范围
-> 状态转换
-> 依赖与交接影响
-> 原子提交
-> 审计与投影事件
```

任一步失败，Revision 不可见。

## 4. 原因码要求

每个拒绝结果必须包含：稳定 code、人类可读说明、失败步骤、是否可重试、权威状态是否改变、最新 Revision（如适用）。不得只返回布尔值。

## 5. 规则版本

提交元数据记录对象 Schema、治理 Policy、指令、Skill 和工具版本。新 Policy 从新提交开始生效，不回写历史 Revision；回退时沿用同样的显式版本选择。

## 6. 失败与恢复

- 任一门禁失败：不发布 Revision，返回失败步骤和稳定原因码。
- Policy 版本不可用：关闭受影响写入，不用其他版本猜测执行。
- 提交结果未知：按幂等键和 current Revision 查询后再决定是否重试。
- 规则回退：从新提交显式使用已验证旧版本，不重解释历史 Revision。

## 7. 验收场景

1. 相同请求使用相同幂等键返回同一治理结果。
2. 任一门禁失败时 current Revision 不变。
3. 可从 Revision 反查实际使用的治理 Policy 和确认记录。
4. 权限、确认和风险三类失败拥有不同稳定原因码。
5. 历史 Revision 不因 Policy 升级而被重新解释为另一状态。
