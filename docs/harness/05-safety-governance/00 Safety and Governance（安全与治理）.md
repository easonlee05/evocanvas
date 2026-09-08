# Safety and Governance（安全与治理）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi 执行保护 + EvoCanvas 确定性治理 + 用户裁决`
> 当前实现状态：`合同已定，代码待迁移`
> 实现说明：Safety 防止危险和误导；Governance 决定信息与动作何时生效。两者由工具与产品规则实现，不建立专用治理 Agent。

## 1. 控制目标

确保 Pi 能主动推进思考，但不能静默升级信息地位、绕过权限、伪造来源、误报执行结果或让未确认内容在 Canvas 和交接中显影。

## 2. 责任分工

| 主体 | 责任 |
| --- | --- |
| Pi | 理解语义、指出冲突、提出候选、解释风险和请求确认 |
| 用户 | 裁决产品含义、作用范围、交接可用性和具体外部行动 |
| Tool Schema / Hooks | 强制身份、权限、版本、来源、状态转换、确认和幂等 |
| Canvas Renderer | 只投影稳定 Revision，显示复核和过时状态 |

## 3. 共同主链

```text
输入/来源
-> 安全检查与来源身份保留
-> Pi 语义分析
-> 用户确认需要稳定化的含义与范围
-> 确定性治理门禁
-> Revision
-> 交接或 Canvas 显影
```

## 4. 失败与恢复

任何不确定性都不得通过“看起来合理”放行：来源不确定保留未验证，确认不清继续澄清，权限不明拒绝执行，副作用结果未知先核对，投影失败保留旧显影。

恢复必须回到对应权威记录：从 Session 恢复过程，从 Revision 恢复稳定状态，从外部回执核对副作用，从 Revision 重建 Canvas。不使用模型摘要或界面状态替代恢复源。

## 5. L3 验收场景

1. Prompt Injection 作为材料进入工作区时不能获得指令权限。
2. Pi 推断的约束未经确认不能稳定化。
3. 用户可接受未验证前提，但交接持续显示风险。
4. 工作包确认不能授权外部发布。
5. Canvas 只能展示已提交 Revision，并准确显示复核或失效状态。

## 6. 子规格

- [Safety（安全）](./01%20Safety%EF%BC%88%E5%AE%89%E5%85%A8%EF%BC%89.md)
- [Governance（治理）](./02%20Governance%EF%BC%88%E6%B2%BB%E7%90%86%EF%BC%89.md)
- [Governance Baseline（治理基线）](./03%20Governance%20Baseline%EF%BC%88%E6%B2%BB%E7%90%86%E5%9F%BA%E7%BA%BF%EF%BC%89.md)
- [Facts and Risk（事实与风险）](./04%20Facts%20and%20Risk%EF%BC%88%E4%BA%8B%E5%AE%9E%E4%B8%8E%E9%A3%8E%E9%99%A9%EF%BC%89.md)
- [Object Governance（对象治理）](./05%20Object%20Governance%EF%BC%88%E5%AF%B9%E8%B1%A1%E6%B2%BB%E7%90%86%EF%BC%89.md)
- [Handoff Governance（交接物治理）](./06%20Handoff%20Governance%EF%BC%88%E4%BA%A4%E6%8E%A5%E7%89%A9%E6%B2%BB%E7%90%86%EF%BC%89.md)
- [Authority and Guardrails（权限与护栏）](./07%20Authority%20and%20Guardrails%EF%BC%88%E6%9D%83%E9%99%90%E4%B8%8E%E6%8A%A4%E6%A0%8F%EF%BC%89.md)
