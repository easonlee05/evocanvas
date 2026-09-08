# Prompt Control（提示控制）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`EvoCanvas 指令制品 + Pi Agent Core`
> 当前实现状态：`部分接入`
> 实现说明：EvoCanvas 发布产品指令制品；Pi 加载、固定本轮版本并负责 Provider 映射。动态业务状态不进入 Prompt。

## 1. 控制目标

保证产品行为规则可版本化、可追溯、可回退，并与 Skills、工具规则、稳定状态和用户原话保持清晰边界。

## 2. Prompt 最小组成

Pi System Instructions 只保留七类稳定内容：

1. 身份与协作关系。
2. 用户拥有最终产品判断。
3. 事实、推断、假设和确认状态必须分开。
4. 冲突与信息缺口必须显性化。
5. 稳定写入必须经过适当确认。
6. 工具结果和来源不得伪造。
7. Canvas 是稳定结构显影，不是事实源。

具体收敛方法进入 Skills；工具参数和确定性限制进入 Tool Schema / Hooks；最新业务状态由 `transformContext` 注入。

## 3. 明确排除

System Instructions 不承载：

- 阶段 Prompt、Supervisor 决定或 Skill 路由结果；
- 当前 Workspace、卡片、工作包或来源正文；
- 当前工具参数和 Provider 序列化细节；
- 每轮固定回执模板；
- 独立结构化输出任务；
- 重试次数、Token 阈值和压缩算法。

EvoCanvas 不构造每轮变化的产品 Developer Prompt。运行环境临时权限由工具可用性、Tool Context 与 Schema 表达；宿主若存在更高优先级开发者指令，Pi 遵守它，但不把它存为工作包事实。

## 4. 规则表达

- `必须 / 不得`：可信性、权限、确认和来源不变量。
- `应当 / 优先`：正常协作默认行为。
- `可以 / 仅在……时`：条件行为和例外。

每条硬规则必须有可观察行为；价值观不能只写抽象名词。自然语言回复按问题复杂度组织，不强制每轮输出固定栏目。

## 5. 发布合同

发布制品：

```text
instruction_bundle_id
semantic_version
content_hash
created_at
released_at
status: draft | active | retired
compatibility: supported_skill_versions + supported_tool_policy_versions
change_summary
```

规则：

1. 只有 `active` 指令包可用于新轮次。
2. 一个新轮次开始时固定 `instruction_bundle_id + version + hash`。
3. 同一 Tool Loop 内不热切换。
4. Revision 提交元数据记录实际使用的指令版本。
5. 回退通过重新激活已验证旧版本完成，不修改历史 Trace 或 Revision。
6. 离线评估只能提出发布候选，不能自动改变 `active` 指针。

## 6. 冲突优先级

```text
宿主系统和安全边界
> Pi System Instructions
> 用户当前请求
> 上下文数据与来源材料
```

Tool Schema / Hooks 不是较低层 Prompt，而是执行面的强制门禁。即使自然语言指令要求执行，工具仍可因权限、版本或确认不足而拒绝。

## 7. 失败与恢复

| 原因码 | 条件 | 行为 |
| --- | --- | --- |
| `instruction.bundle_missing` | active 指针无对应制品 | 不启动稳定写入能力 |
| `instruction.hash_mismatch` | 内容与发布哈希不符 | 拒绝使用并告警 |
| `instruction.incompatible_resources` | Skill / Tool policy 不兼容 | 关闭受影响能力，不静默降级规则 |
| `instruction.mid_turn_changed` | 本轮检测到版本变化 | 本轮继续固定旧版本，下轮使用新版本 |
| `instruction.rollback_failed` | 旧版本不可恢复 | 保持当前已知可用版本，禁止发布未知版本 |

## 8. 验收场景

1. 工作包正文包含 Prompt Injection 时，仍只被当作上下文数据。
2. 工具列表变化不需要修改 System Instructions 正文。
3. 指令新版本在一次 Tool Loop 中发布，不影响该 Loop 的后续模型调用。
4. 某 Revision 能追溯到当时实际使用的指令包和 Skill 版本。
5. 离线评估标记新版本较优，但没有发布动作时线上指针保持不变。
