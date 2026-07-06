#!/bin/bash

# Codex Prompt 数据提取脚本
# 从 rollout JSONL 中提取系统提示、工具定义和对话轮次

set -e

WORKDIR="/tmp/claude-501/evocanvas-codex-lab"
START_TS=$(cat "$WORKDIR/experiment-start-timestamp.txt")

echo "=== 开始提取 Codex Prompt 数据 ==="
echo "实验开始时间戳: $START_TS"
echo ""

# 查找实验开始后的所有 rollout 文件
echo ">>> 查找新生成的 rollout 文件..."
ROLLOUT_FILES=$(find ~/.codex/sessions/2026 -name "rollout-*.jsonl" -newer "$WORKDIR/experiment-start-timestamp.txt" 2>/dev/null || echo "")

if [ -z "$ROLLOUT_FILES" ]; then
  echo "错误: 没有找到新的 rollout 文件"
  echo "请检查:"
  echo "  1. Codex 命令是否成功执行"
  echo "  2. 是否传了 --ephemeral 参数（会导致不写入 rollout）"
  echo "  3. 会话目录权限: ls -la ~/.codex/sessions/"
  exit 1
fi

echo "找到以下 rollout 文件:"
echo "$ROLLOUT_FILES" | nl
echo ""

# 创建提取目录
mkdir -p "$WORKDIR/extracted"

# 按场景编号提取（假设文件按时间顺序）
COUNTER=1
for ROLLOUT in $ROLLOUT_FILES; do
  echo ">>> 提取场景 $COUNTER: $(basename $ROLLOUT)"

  # 提取 base_instructions（系统提示）
  echo "  - 提取系统提示..."
  jq -r 'select(.payload.base_instructions != null) | .payload.base_instructions.text' "$ROLLOUT" \
    > "$WORKDIR/extracted/scenario${COUNTER}-base-instructions.txt" 2>/dev/null || echo "无 base_instructions"

  # 提取 dynamic_tools（工具定义）
  echo "  - 提取工具定义..."
  jq 'select(.payload.dynamic_tools != null) | .payload.dynamic_tools' "$ROLLOUT" \
    > "$WORKDIR/extracted/scenario${COUNTER}-dynamic-tools.json" 2>/dev/null || echo "无 dynamic_tools"

  # 提取所有对话轮次
  echo "  - 提取对话轮次..."
  jq 'select(.type == "turn") | {role: .payload.role, content: .payload.content}' "$ROLLOUT" \
    > "$WORKDIR/extracted/scenario${COUNTER}-turns.jsonl" 2>/dev/null || echo "无对话轮次"

  # 完整的 rollout 副本
  cp "$ROLLOUT" "$WORKDIR/extracted/scenario${COUNTER}-full-rollout.jsonl"

  echo "  ✓ 场景 $COUNTER 提取完成"
  echo ""

  COUNTER=$((COUNTER + 1))
done

echo "=== 提取完成 ==="
echo ""
echo "结果目录: $WORKDIR/extracted/"
echo ""
echo "快速查看系统提示（场景1）："
echo "  head -50 $WORKDIR/extracted/scenario1-base-instructions.txt"
echo ""
echo "查看工具定义（场景1）："
echo "  jq '.[0]' $WORKDIR/extracted/scenario1-dynamic-tools.json"
