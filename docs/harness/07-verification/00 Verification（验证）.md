# Verification（验证）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`EvoCanvas 确定性验证器 + Pi 技术校验`
> 当前实现状态：`原生验证链已接入，端到端证据待补齐`
> 实现说明：Verification 判断一次读取、提交、交接或投影是否满足已定义合同；不建立第二模型裁决产品语义。

## 1. 控制目标

在状态或副作用生效前证明结构、来源、权限、确认、版本和策略均有效，并在生效后证明 Revision 与投影结果一致。

## 2. 三类验证

| 类别 | 回答 | 权威输入 |
| --- | --- | --- |
| Structure Verification | 对象、关系、状态和 Revision 是否结构有效 | Schema + base Revision + operations |
| Source Verification | 来源是否可定位、完整、核验状态是否如实 | source refs + Tool Results |
| Policy Verification | 主体、确认、风险和转换是否允许生效 | identity + confirmations + policy version |

语义“是否是用户真正想要的”通过用户确认解决，不由确定性验证器或第二 LLM 假装证明。

## 3. 验证时点

```text
读取前：身份与范围
上下文装配：Revision 和快照结构
工具前：Schema、权限、确认、幂等
Session 创建：submission/content hash、Binding 状态、单 Session 文件和宿主锁
提交内：结构、来源、状态、依赖、Policy
提交后：完整 Revision 和 current 指针
投影后：projected Revision 与确定性差异
交接前：范围、未决、风险和确认
```

## 4. 验证结果合同

```text
verification_id
subject_type
subject_id
policy_or_schema_version
status: passed | failed | unavailable
checks[]: code + status + evidence_refs[]
blocking_reasons[]
created_at
```

`unavailable` 不得被当作 `passed`。每个 blocking reason 必须映射到稳定原因码和可恢复动作。

## 5. 原子边界

工作包提交内的阻断性验证必须与 Revision 创建原子执行。提交后验证若发现存储损坏或指针不一致，立即阻止进一步写入并进入修复；不得创建“部分有效”业务版本。

## 6. 失败与恢复

- 验证器不可用：关闭对应写入或高风险动作；只读和普通对话按风险降级。
- Schema / Policy 版本缺失：不得使用最新版本猜测解释历史请求。
- 提交后验证失败：隔离故障 Revision 指针并从最后完整版本恢复，保留审计。
- 投影验证失败：Revision 保持有效，重建投影。
- 来源核验不可用：保持未验证状态，不阻断用户明确接受风险的内部决定。

## 7. L3 验收场景

1. 缺少来源引用的证据对象不能通过结构和来源验证。
2. 用户已确认但无权限，Policy Verification 仍失败。
3. 验证器超时不等于通过。
4. 未验证前提在风险接受后可进入交接，但验证结果仍显示 unverified。
5. Canvas 投影内容与目标 Revision 不一致时，不标记 ready。
6. 相同 `submission_id` 不同内容哈希被拒绝；相同内容重试只对应一个 Entry。
7. 工具缺失或无法读取 replay 策略时按 `never`，验证器不会把 `unknown` 判为可自动重放。

## 8. 子规格

- [Structure Verification（结构验证）](./01%20Structure%20Verification%EF%BC%88%E7%BB%93%E6%9E%84%E9%AA%8C%E8%AF%81%EF%BC%89.md)
- [Source Verification（来源验证）](./02%20Source%20Verification%EF%BC%88%E6%9D%A5%E6%BA%90%E9%AA%8C%E8%AF%81%EF%BC%89.md)
- [Policy Verification（策略验证）](./03%20Policy%20Verification%EF%BC%88%E7%AD%96%E7%95%A5%E9%AA%8C%E8%AF%81%EF%BC%89.md)
