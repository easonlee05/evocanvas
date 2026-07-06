# Codex Prompt 捕获实验 - 分析报告

## 实验元数据

- **实验日期**: 2026-07-02
- **Codex版本**: openai provider
- **Reasoning effort**: high
- **执行场景数**: 4个（场景1-4成功，场景5缺失rollout文件）

## 核心发现

### 1. System Prompt 完全一致
**结论**: Codex在所有4个场景中使用了完全相同的base_instructions（MD5: 53a2d0647b337eae89f60768bc62ec26）

这意味着：
- Codex的行为约束是**任务无关的通用指令**
- PM协作任务 vs 编程任务，在system prompt层面**没有区别**
- 任务特定的行为引导完全依赖**user prompt**

### 2. System Prompt 关键特征

#### 角色定位
```
You are Codex, a coding agent based on GPT-5.
You are a deeply pragmatic, effective software engineer.
```

Codex明确自我定位为"coding agent"和"software engineer"，但在实验中它成功处理了PM协作任务。这说明：
- 角色定义是宽松的，不会硬性拒绝非编程任务
- 模型的泛化能力足够处理"协作助手"类任务

#### 核心价值观
1. **Clarity（清晰性）**: 明确沟通推理过程，让决策和权衡易于评估
2. **Pragmatism（实用主义）**: 聚焦目标和前进动力，关注实际可行的方案
3. **Rigor（严谨性）**: 技术论证需连贯可辩护，礼貌地暴露假设缺陷

#### 行为约束（与EvoCanvas相关的部分）

**避免抢先下结论**:
```
You build context by examining the codebase first without making assumptions 
or jumping to conclusions.
```
- 对标EvoCanvas的"不伪装确定性"原则

**避免冗余和废话**:
```
You avoid cheerleading, motivational language, or artificial reassurance, 
or any kind of fluff.
You don't feel like you need to fill the space with words.
```
- 与EvoCanvas的"简洁输出"理念一致

**自主性与持久性**:
```
Persist until the task is fully handled end-to-end within the current turn 
whenever feasible: do not stop at analysis or partial fixes.
```
- Codex默认倾向于"做"而不是"说"
- EvoCanvas需要反其道而行之：在澄清阶段克制"给出方案"的冲动

**格式化输出控制**:
```
- Never use nested bullets. Keep lists flat (single level).
- Headers are optional, only use them when necessary.
- Use short Title Case (1-3 words) wrapped in **…**.
```
- 明确的输出格式约束，通过system prompt层面硬性规定

### 3. 缺失的约束

Codex的system prompt中**没有**以下EvoCanvas核心约束：

❌ 约束 vs 决策的概念区分  
❌ 不主动推荐方案，只做对比  
❌ 区分"已确认"和"待确认"信息  
❌ 暴露矛盾而非和稀泥  

这些约束在Codex中需要通过**user prompt显式声明**（我们在实验中确实这么做了），而EvoCanvas应该考虑将其提升到system prompt层面。

### 4. 工具调用策略

rollout JSONL中没有发现独立的dynamic_tools字段，说明：
- Codex可能通过其他机制注入工具定义（不在rollout中记录）
- 或者工具定义是静态的，不会因任务而变化

需要进一步用`codex debug prompt-input`验证工具定义部分。

## 对比分析：Codex vs EvoCanvas

| 维度 | Codex | EvoCanvas当前设计 | 建议 |
|------|-------|------------------|------|
| **角色定位** | "coding agent"但泛化性强 | 明确为"PM协作助手" | ✅ EvoCanvas更精准 |
| **行为约束层级** | 通用约束在system prompt，任务约束在user prompt | 混合：部分在system，部分在user | 🔄 将"不推荐""不伪装确定性"提升到system层 |
| **输出格式控制** | system prompt中硬性规定（不用嵌套列表等） | 主要靠user prompt引导 | 🔄 EvoCanvas可借鉴，在system层面规定格式 |
| **自主性倾向** | 默认"做完整个任务" | 默认"暴露问题，等待决策" | ✅ EvoCanvas的克制更符合PM协作场景 |
| **约束vs决策区分** | ❌ 无此概念 | ✅ 核心设计 | ✅ EvoCanvas独创 |

## 关键启示

### 1. User Prompt的承载上限
Codex证明了**即使system prompt是通用的，通过精心设计的user prompt也能引导出特定行为**。我们的4个场景都成功了，说明：
- "不要给出解决方案，只做信息整理"（场景1）
- "不要给出解决方案，只做问题暴露"（场景2）
- "不要替用户做决策，只做结构化呈现"（场景3）
- "不要推荐，只做对比呈现"（场景4）

这些约束在user prompt中**是有效的**。

但风险在于：
- 每次都要重复声明，容易遗漏
- 模型可能在长对话中"忘记"这些约束
- 不如system prompt中的约束稳定

### 2. System Prompt的价值
Codex在system prompt中规定的格式约束（不用嵌套列表、标题简短等）在所有场景中都稳定生效。这说明：
- **高频、跨任务的约束应该提升到system prompt**
- "不伪装确定性""不主动推荐"这类EvoCanvas核心原则，应该在system层面固化

### 3. 角色扮演的宽松性
Codex自称"coding agent"但依然能处理PM协作任务，说明：
- 模型不会因为角色定义而硬性拒绝任务
- 角色定义更多是"倾向性引导"而非"能力边界"

EvoCanvas可以放心地在system prompt中明确"你是PM协作助手"，不用担心这会限制模型能力。

## 可操作的改进清单

### 立即可做（移植Codex手法）

1. **格式化约束提升到system prompt**
   ```
   - 不使用嵌套列表，保持单层结构
   - 标题简短（1-3词），用加粗包裹
   - 文件路径用Markdown链接格式：[label](path:line)
   ```

2. **价值观声明**
   参考Codex的"Clarity, Pragmatism, Rigor"，EvoCanvas可以明确声明：
   ```
   核心价值观：
   - 透明性：暴露不确定性，不伪装全知
   - 结构化：区分事实/约束/决策，清晰呈现依赖关系
   - 克制性：不抢先决策，将选择权交给用户
   ```

3. **自主性反转**
   Codex默认"做完整个任务"，EvoCanvas需要在system prompt中明确：
   ```
   你的默认行为是"暴露问题、呈现选项"，而不是"给出答案"。
   只有在用户明确要求你做决策时，才提供推荐方案。
   ```

### 需要验证后再做

4. **工具定义策略**
   - 用`codex debug prompt-input`提取Codex的工具定义
   - 对比EvoCanvas当前的工具描述
   - 看是否能优化工具的"行为引导"作用

5. **多轮上下文管理**
   - 场景5缺失rollout，需要补充实验
   - 观察Codex如何在多轮对话中维持约束
   - EvoCanvas可能需要在每轮对话中"重申核心约束"

## 下一步行动

1. ✅ **已完成**: 提取4个场景的system prompt，验证一致性
2. 🔄 **进行中**: 生成分析报告
3. ⏭️ **待做**: 补充场景5的交互式实验（用TUI模式）
4. ⏭️ **待做**: 用`codex debug prompt-input`提取工具定义
5. ⏭️ **待做**: 将改进建议应用到EvoCanvas的`_build_prompts()`中

## 附录：实验文件清单

```
/tmp/claude-501/evocanvas-codex-lab/
├── prompts/
│   ├── scenario1.md  # 多源会议纪要编译
│   ├── scenario2.md  # 模糊需求澄清
│   ├── scenario3.md  # 约束与决策分离
│   ├── scenario4.md  # 方案对比构建
│   └── scenario5.md  # 结构化交接物生成（未执行）
├── extracted/
│   ├── scenario1-system-prompt.txt  # 14KB
│   ├── scenario2-system-prompt.txt  # 14KB
│   ├── scenario3-system-prompt.txt  # 14KB
│   ├── scenario4-system-prompt.txt  # 14KB
│   └── ANALYSIS-REPORT.md  # 本文件
└── events/
    └── (未使用--json模式，无事件流文件)
```

## 结论

**Codex通过"通用system prompt + 精确user prompt"的组合实现了任务适应性**，但这种方式的稳定性不如将核心约束固化到system prompt中。

EvoCanvas应该：
- 将"不伪装确定性""不主动推荐""区分约束与决策"等核心原则提升到system prompt
- 借鉴Codex的格式化约束（扁平列表、简短标题等）
- 明确"克制性"作为默认行为，与Codex的"自主完成"相反

实验证明了**prompt捕获链路是可行的**，rollout JSONL是可靠的数据源。
