# EvoCanvas Prompt Engineering（提示工程）

> 当前成熟度层级：`L2 对象与流程定义层`
> 使用方式：`作为与 harness 平行的横切工程面文档，不替代 harness 七层设计`

## 1. 文档目的

本文档只做一件事：

- 定义 EvoCanvas 1.0 中 `prompt engineering` 的职责边界、模块骨架与控制关系

本文档不做这些事：

- 不把 `prompt engineering` 写成 harness 第八层
- 不把 `prompt engineering` 冒充为产品主方法论
- 不把具体提示词文案提前写成实现终稿

因此，这是一份“语言接口编排设计文档”，不是“七层 harness 替代文档”。

## 2. 在 EvoCanvas 中它是什么

在 EvoCanvas 1.0 中，`prompt engineering` 不是“写几段好 prompt”，而是：

- 把 harness 已定义好的阶段目标、对象约束、验证要求与治理边界
- 稳定翻译成 `LLM` 可执行行为的语言接口工程

一句话说：

- `prompt engineering` 的职责，不是优化说法，而是约束行为

它与 harness 的关系不是上下级替代关系，而是：

- harness 定义系统必须具备哪些控制能力
- `prompt engineering` 负责把这些控制能力传递给模型执行

因此，它与 `docs/harness/` 平行建档，但不与 harness 并列成“两套主骨架”。

## 3. 与 harness、上下文工程、循环工程的边界

从工程控制面看，EvoCanvas 当前建议做如下区分：

- `prompt engineering`：控制模型此步该如何被驱动与约束
- `context engineering`：控制模型此步能看到什么信息
- harness engineering：控制系统如何组织工具、状态、验证、治理与交接
- loop engineering：控制系统如何跨时间推进、回流、停机与自我修正

这里的关系更接近“不同控制面”，而不是严格树状学术层级。

对 EvoCanvas 来说，当前最重要的是先把以下边界钉住：

- `prompt engineering` 不定义产品目标
- `prompt engineering` 不定义七层职责
- `prompt engineering` 不拥有最终验证权或治理放行权
- `prompt engineering` 不把模型内部推理过程直接当成交付对象

## 4. 核心设计目标

EvoCanvas 的 `prompt engineering` 首要目标不是“让回答更像专家”，而是：

- 让模型少越权
- 让模型少跳步
- 让模型少伪装确定性
- 让模型更稳定地产出结构化中间物

因此，它应优先服务以下目标：

- 阶段内动作正确
- 输出对象正确
- 风险边界显性化
- 回执与交接可继续推进

## 5. 模块级骨架

EvoCanvas 当前建议将 `prompt engineering` 拆成四类模块：

1. 系统基座提示（system base prompt）
2. 阶段提示（stage prompt）
3. 对象提示（object prompt）
4. 回执 / 交接提示（receipt / handoff prompt）

这四类不是四套并行小系统，而是有主从关系的控制骨架。

当前主干口径是：

- `系统基座提示 + 阶段提示` 共同构成主控骨架
- `对象提示` 与 `回执 / 交接提示` 作为挂载模块按需启用

这意味着：

- 系统基座提示负责全局不变规则
- 阶段提示负责当前回合的动作边界
- 对象提示负责把输出压到正确对象上
- 回执 / 交接提示负责把结果收束成可验证、可治理、可继续推进的形式

四类模块的展开见：

- [01 System Base Prompt（系统基座提示）.md](</Users/apple/Desktop/evocanvas/docs/prompt-engineering/01 System Base Prompt（系统基座提示）.md>)
- [02 Stage Prompt（阶段提示）.md](</Users/apple/Desktop/evocanvas/docs/prompt-engineering/02 Stage Prompt（阶段提示）.md>)
- [03 Object Prompt（对象提示）.md](</Users/apple/Desktop/evocanvas/docs/prompt-engineering/03 Object Prompt（对象提示）.md>)
- [04 Receipt and Handoff Prompt（回执与交接提示）.md](</Users/apple/Desktop/evocanvas/docs/prompt-engineering/04 Receipt and Handoff Prompt（回执与交接提示）.md>)

## 6. 主控骨架与挂载关系

### 6.1 系统基座提示

系统基座提示负责声明全局不变立场，例如：

- 透明优先
- 不得静默合并冲突
- 不得把草稿伪装成稳定结论
- 必须优先暴露未决问题、冲突边界、未确认前提与收敛置信度

它不回答“当前这一步做什么”，只回答“无论在哪一步，都不能越过什么边界”。

### 6.2 阶段提示

阶段提示负责回答：

- 当前处于哪一阶段
- 当前阶段允许做什么
- 当前阶段不允许越级做什么
- 当前阶段的最小输出应落到哪类对象

因此，阶段提示是运行中最直接的动作控制面。

### 6.3 对象提示

对象提示负责把模型自由生成压缩成特定对象语义，例如：

- 来源片段（source fragment）
- 解释对象（interpretation）
- 待澄清项（clarification）
- 约束（constraint）
- 待决策候选（decision candidate）

它不决定当前阶段是否允许生成这些对象，只负责在被允许时把对象做对。

### 6.4 回执 / 交接提示

回执 / 交接提示负责：

- 整理当前结果的可见边界
- 输出最小风险披露
- 将结果整理为后续可验证、可治理、可交接的形式

它不拥有最终放行权，只负责把结果整形成可进入后续控制链的形态。

## 7. 与 `思维链（CoT）` 的边界

`思维链（CoT）` 不是 EvoCanvas `prompt engineering` 的主对象。

它最多只是：

- 某些 prompt 在内部可能调用的一类推理展开策略

但在 EvoCanvas 1.0 中：

- 不默认要求对外暴露完整内部推理
- 不把 `思维链（CoT）` 单独当成治理依据
- 不把 `思维链（CoT）` 等同于透明性

EvoCanvas 真正要求显性化的，是：

- 未决问题
- 冲突边界
- 未确认前提
- 当前收敛置信度

## 8. 当前设计禁令

以下做法应被视为 `prompt engineering` 的设计禁令：

- 把 `prompt engineering` 写成 harness 第八层
- 用 prompt 偷偷替代验证与治理
- 让阶段提示越权覆盖系统基座规则
- 让对象提示直接决定对象生效
- 把回执提示写成“自动把草稿包装成结论”
- 把 `思维链（CoT）` 误当成对外主交付对象

## 9. 当前 L2 结论

截至当前版本，EvoCanvas 关于 `prompt engineering` 的主干结论如下：

- `prompt engineering` 与 `docs/harness/` 平行建档
- 它是横切工程面，不是 harness 第八层
- 它当前采用四模块骨架
- `系统基座提示 + 阶段提示` 构成主控骨架
- `对象提示` 与 `回执 / 交接提示` 构成挂载模块
- 其首要目标是约束行为，而不是美化答案
