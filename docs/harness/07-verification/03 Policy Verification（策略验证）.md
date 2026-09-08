# Policy Verification（策略验证）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`身份能力、确认解析器、治理 Policy 与 Tool Hooks`
> 当前实现状态：`合同已定，代码待迁移`
> 实现说明：策略验证是确定性门禁，不调用 LLM 判断是否放行。

## 1. 控制目标

保证稳定写入、交接确认和外部行动符合当时已发布的权限、确认、风险和状态转换规则。

## 2. 输入

```text
actor identity and capabilities
action / tool and target scope
base revision and current revision
operations or external parameters
confirmation refs
risk refs
policy version
idempotency key
```

身份由 Runtime 注入；模型提供的同名字段不可信。

## 3. 检查顺序

1. Policy 版本存在且适用于当前动作。
2. 主体身份有效且拥有目标范围能力。
3. 基础 Revision 未过时。
4. 确认发生在内容展示之后，主体和动作匹配。
5. 确认的内容哈希、范围和风险完整。
6. 状态转换和工具副作用等级允许。
7. 幂等键未与不同请求冲突。
8. 必需审计能力可用。

## 4. 结果

`passed` 只对本次精确输入有效，不生成可泛化的永久授权。修改目标、关键参数、内容、范围、Revision 或风险后必须重新验证。

## 5. 策略变化

新 Policy 仅用于新动作。历史 Revision 保留当时 Policy 版本和结果。紧急撤销权限对后续工具调用立即生效，但不修改已完成动作的历史结论。

## 6. 失败与恢复

| 原因码 | 行为 |
| --- | --- |
| `policy.version_missing` | 拒绝动作，不用最新规则猜测 |
| `policy.permission_denied` | 返回缺失能力和允许披露的范围 |
| `policy.confirmation_mismatch` | 重新展示并确认受影响内容 |
| `policy.risk_incomplete` | 补齐风险接受或保持阻断 |
| `policy.audit_unavailable` | 阻止要求强审计的动作 |
| `policy.idempotency_conflict` | 拒绝同键不同请求 |

## 7. 验收场景

1. 有确认但无权限时验证失败。
2. 有权限但确认内容哈希过时时验证失败。
3. 交接确认不能通过同一记录授权外部发布。
4. 历史 Revision 可还原当时实际 Policy 版本。
5. 模型高置信或自然语言“已批准”不能代替确认记录。
