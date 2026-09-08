# Instructions and Context（指令与上下文）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi Agent Core + EvoCanvas 产品能力`
> 当前实现状态：`部分接入`
> 实现说明：Pi 是唯一 Agent 核心；EvoCanvas 向 Pi 提供稳定指令、Skills、工具与结构化工作包投影，不在 Pi 前面组装另一个 Prompt 或运行时。

## 1. 控制目标

本组保证 Pi 始终能分清两件事：

- **Instructions** 决定应该如何理解、判断和行动。
- **Context** 决定当前基于哪些过程记录和稳定事实工作。

二者不得被混成一段来源不明的 Prompt，也不得用 Canvas 或卡片文案反向提升信息地位。

## 2. 权威输入与输出

| 逻辑面 | 权威来源 | 用途 | 是否持久进 Session |
| --- | --- | --- | --- |
| Pi System Instructions | 发布的指令包 | 稳定产品原则和不变量 | 记录版本引用，不重复追加全文 |
| Skills | 发布的 Skill 资源 | 按需工作方法 | 记录实际使用的 Skill 版本 |
| Primary Pi Session | Pi Session Entry | 原始 user / assistant / tool 过程真相 | 是 |
| Workspace Context Snapshot | 最新结构化工作包 Revision | 当前稳定工作锚点 | 否，每次调用前临时生成 |
| Tool Schema / Hooks | Pi 工具注册和 EvoCanvas 确定性规则 | 参数、权限、状态转换与副作用门禁 | 记录调用与结果 |

当前用户输入必须作为原始 User Entry 进入 Primary Pi Session，不得拼入内部阶段、对象摘要或输出格式后冒充用户原话。

## 3. 主链

```text
用户提交原始输入
-> Pi 保存 User Entry
-> transformContext 临时注入最新稳定工作快照
-> Pi 按需读取 Skill 和调用工具
-> Pi 自然语言回复或提出需确认的结构变更
-> 用户确认后，Pi 通过受治理的 workspace.commit 提交 Revision
-> Canvas 只显影新的稳定 Revision
```

不存在独立 `run_chat`、`run_convergence`、Product Kernel 或 Context Manifest。

## 4. 权限和确认边界

1. System Instructions 和 Skills 可约束 Pi 行为；业务材料、工具结果和 Workspace Context Snapshot 只是数据。
2. Pi 可在 Session 中自由推测、比较和起草，但不得因为某个 Skill 要求而跳过用户确认。
3. 只有来源事实的完整性收录和已确认的语义变更可进入稳定工作包。
4. Canvas 只消费稳定 Revision，不以临时 Session 内容生成正式卡片。

## 5. 失败与恢复

- 稳定工作快照读取失败：保留用户本轮输入并允许对话，但关闭稳定写入，明确提示已降级。
- 指令包或必需 Skill 无法解析：不使用未知默认值替代；本轮可退化为普通对话，不得提交稳定结构。
- 工具读取失败：保留原始 Tool Result 和失败原因，不伪造已读取结果。
- 提交后上下文未更新：以 Revision 读取结果为准，不靠向 Session 补写一份摘要修复。

## 6. L3 验收场景

1. 工作包中出现“忽略上述规则”时，Pi 将其当作业务材料而非指令。
2. 用户修改同一结构化工作包后，Pi 下轮通过最新 Revision 看到变化，无需额外“通知 Pi”。
3. Pi 在 Session 中提出候选约束时，Canvas 不显影；用户确认并提交后才显影。
4. `transformContext` 失败时，用户输入仍在 Session 中，且 `workspace.commit` 不可用。
5. 更换 Provider 时，不改变上述逻辑面的信息地位。

## 7. 子规格

- [Instructions（指令）](./01%20Instructions%EF%BC%88%E6%8C%87%E4%BB%A4%EF%BC%89.md)
- [Context（上下文）](./02%20Context%EF%BC%88%E4%B8%8A%E4%B8%8B%E6%96%87%EF%BC%89.md)
- [Context Assembly（上下文装配）](./03%20Context%20Assembly%EF%BC%88%E4%B8%8A%E4%B8%8B%E6%96%87%E8%A3%85%E9%85%8D%EF%BC%89.md)
- [AI Assistant Working Surface（AI 助手工作面）](./04%20AI%20Assistant%20Working%20Surface%EF%BC%88AI%20%E5%8A%A9%E6%89%8B%E5%B7%A5%E4%BD%9C%E9%9D%A2%EF%BC%89.md)
- [Prompt Control（提示控制）](./05%20Prompt%20Control%EF%BC%88%E6%8F%90%E7%A4%BA%E6%8E%A7%E5%88%B6%EF%BC%89.md)
- [Context Budget and Compaction（上下文预算与压缩）](./06%20Context%20Budget%20and%20Compaction%EF%BC%88%E4%B8%8A%E4%B8%8B%E6%96%87%E9%A2%84%E7%AE%97%E4%B8%8E%E5%8E%8B%E7%BC%A9%EF%BC%89.md)
