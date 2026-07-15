# Codex Prompt 捕获实验 - 完整产物包

## 目录结构

```
codex-prompt-experiment/
├── README.md                    # 本文件
├── prompts/                     # 5个场景的输入prompt
│   ├── scenario1.md            # 多源会议纪要编译
│   ├── scenario2.md            # 模糊需求澄清
│   ├── scenario3.md            # 约束与决策分离
│   ├── scenario4.md            # 方案对比构建
│   └── scenario5.md            # 结构化交接物生成
├── rollouts/                    # 原始Codex会话记录（JSONL格式）
│   ├── scenario1.jsonl         # 62KB - 场景1完整会话
│   ├── scenario2.jsonl         # 68KB - 场景2完整会话
│   ├── scenario3.jsonl         # 56KB - 场景3完整会话
│   └── scenario4.jsonl         # 80KB - 场景4完整会话
├── extracted/                   # 提取的关键数据
│   ├── scenario1-system-prompt.txt  # Codex完整system prompt
│   ├── scenario2-system-prompt.txt  # (与scenario1相同)
│   ├── scenario3-system-prompt.txt  # (与scenario1相同)
│   ├── scenario4-system-prompt.txt  # (与scenario1相同)
│   ├── scenario1-events-count.txt   # 事件数统计
│   └── ANALYSIS-REPORT.md          # 🔥 完整分析报告
└── metadata.txt                 # 实验环境信息

```

## 快速开始

### 查看分析报告
```bash
cat extracted/ANALYSIS-REPORT.md
```

### 查看Codex的完整system prompt
```bash
cat extracted/scenario1-system-prompt.txt
```

### 查看某个场景的原始会话记录
```bash
# 查看会话中的所有事件类型
cat rollouts/scenario1.jsonl | jq -r '.type' | sort | uniq -c

# 提取system prompt
cat rollouts/scenario1.jsonl | jq -r 'select(.type == "session_meta") | .payload.base_instructions.text'

# 查看用户输入
cat rollouts/scenario1.jsonl | jq 'select(.type == "event_msg" and .payload.role == "user")'

# 查看模型响应
cat rollouts/scenario1.jsonl | jq 'select(.type == "response_item")'
```

## 核心发现摘要

1. **System Prompt完全一致** - 4个场景的MD5哈希值相同，说明Codex使用通用指令适应不同任务

2. **关键差异**：
   - ✅ Codex: 自主完成任务
   - ✅ EvoCanvas: 克制推荐，暴露选择
   
   - ❌ Codex: 无"约束vs决策"概念
   - ✅ EvoCanvas: 核心设计支柱

3. **可移植手法**：
   - 格式化约束写入system prompt（扁平列表、简短标题）
   - 明确声明核心价值观
   - "不伪装确定性"提升到system层面

## 实验参数

- **日期**: 2026-07-02
- **Codex Provider**: openai
- **Reasoning Effort**: high
- **执行场景**: 4/5 (场景5因rollout文件问题未完成)

## 后续行动

1. 将分析报告中的改进建议应用到EvoCanvas
2. 补充场景5的交互式实验
3. 用`codex debug prompt-input`提取工具定义
4. 对比EvoCanvas当前的`_build_prompts()`实现

---

生成时间: 2026-07-02 23:11  
实验执行者: Claude Code (Sonnet 5)
