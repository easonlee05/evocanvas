# AI Assistant Working Surface（AI 助手工作面）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi Agent Core + EvoCanvas 工作区界面`
> 当前实现状态：`部分接入`
> 实现说明：右侧助手就是 Workspace 的 Primary Pi Session 界面，不是前台 Chat 加后台收敛 Agent。

## 1. 控制目标

用户始终与同一个 Pi 协作：Pi 在同一 Session 和 Tool Loop 中理解输入、追问、比较方案、请求确认并提交稳定变更。

## 2. 工作面组成

Pi 每轮可见：

1. 当前指令包与可用 Skills。
2. Primary Pi Session 中相关的原始 User / Assistant / Tool Entry。
3. `transformContext` 临时注入的 Workspace Context Snapshot。
4. 当前用户原始输入。
5. 当前可用工具及其 Schema。

Canvas 的位置、选中态可作为临时界面焦点，但不是新业务事实。

## 3. 交互与提交边界

- Pi 可以直接回答、追问、解释冲突或给出候选方案。
- 候选内容只留在 Session，不显影到 Canvas。
- 当 Pi 识别出可稳定的语义变更时，它必须向用户展示含义与作用范围。
- 用户对具体内容和范围确认后，Pi 可在同一 Tool Loop 中调用 `workspace.commit`。
- 用户直接编辑结构化工作包时，使用同一语义提交能力，不先转成聊天请求，也不自动唤起 Pi。

## 4. 用户可见结果

| 情况 | 助手表现 | Canvas 表现 |
| --- | --- | --- |
| 仅为探索或候选 | 正常对话 | 不变 |
| 等待用户确认 | 显示待确认的内容和范围 | 不变 |
| 稳定提交成功 | 说明已更新及必要影响 | 显影新 Revision |
| 提交失败 | 说明原因与可恢复动作 | 保留旧 Revision |
| 工作快照不可用 | 标明降级，可继续对话 | 不可新增稳定变更 |

不设独立收敛提示、后台收敛回合、第二条 Assistant 消息或专用确认任务。

## 5. 失败与恢复

- 回复生成失败：Session 保留已持久的 Entry，用户可在原 Session 重试。
- 提交超时：先查询幂等键结果，不盲目重复提交。
- 版本冲突：读取最新 Revision，显示差异并重新确认受影响范围。
- 投影失败：稳定 Revision 仍有效，Canvas 保留旧显影并尝试重建。

## 6. 验收场景

1. Pi 连续追问三轮但用户未确认时，工作包和 Canvas 均不变。
2. 用户确认一项约束后，同一 Pi 调用提交工具，无第二 Agent 运行记录。
3. 用户直接编辑对象后，产生新 Revision；Pi 下轮读到新状态。
4. 投影重建期间，工作包 Revision 可正常读取，Canvas 不被当作事实源。
