#!/bin/bash

# Codex Prompt 捕获实验 - 执行脚本
# 使用方法：在你的终端中运行 bash /tmp/claude-501/evocanvas-codex-lab/run-experiments.sh

set -e

WORKDIR="/tmp/claude-501/evocanvas-codex-lab"
echo "=== Codex Prompt 捕获实验开始 ==="
echo "工作目录: $WORKDIR"
echo ""

# 场景1：多源会议纪要编译
echo ">>> 执行场景1: 多源会议纪要编译"
codex exec -c 'service_tier="fast"' \
  --json \
  -o "$WORKDIR/outputs/scenario1-output.md" \
  "$(cat $WORKDIR/prompts/scenario1.md)" \
  > "$WORKDIR/events/scenario1-events.jsonl" 2>&1

echo "✓ 场景1完成"
echo ""

# 场景2：模糊需求澄清
echo ">>> 执行场景2: 模糊需求澄清"
codex exec -c 'service_tier="fast"' \
  --json \
  -o "$WORKDIR/outputs/scenario2-output.md" \
  "$(cat $WORKDIR/prompts/scenario2.md)" \
  > "$WORKDIR/events/scenario2-events.jsonl" 2>&1

echo "✓ 场景2完成"
echo ""

# 场景3：约束与决策分离
echo ">>> 执行场景3: 约束与决策分离"
codex exec -c 'service_tier="fast"' \
  --json \
  -o "$WORKDIR/outputs/scenario3-output.md" \
  "$(cat $WORKDIR/prompts/scenario3.md)" \
  > "$WORKDIR/events/scenario3-events.jsonl" 2>&1

echo "✓ 场景3完成"
echo ""

# 场景4：方案对比构建
echo ">>> 执行场景4: 方案对比构建"
codex exec -c 'service_tier="fast"' \
  --json \
  -o "$WORKDIR/outputs/scenario4-output.md" \
  "$(cat $WORKDIR/prompts/scenario4.md)" \
  > "$WORKDIR/events/scenario4-events.jsonl" 2>&1

echo "✓ 场景4完成"
echo ""

echo "=== 前4个场景执行完毕 ==="
echo ""
echo "注意：场景5需要多轮上下文，请手动执行交互式命令："
echo "  codex -c 'service_tier=\"fast\"'"
echo "然后在交互界面中依次输入场景1-4的内容，最后输入场景5的内容"
echo ""
echo "执行完毕后，运行提取脚本："
echo "  bash $WORKDIR/extract-prompts.sh"
