#!/bin/bash
# Codex Prompt 采集脚本 — 配合 claude-tap 使用
# 用法: bash capture.sh [场景编号 1-5]
# 不传编号则执行全部 5 个场景

set -e

# 确保 PATH 包含 claude-tap
source "$HOME/.local/bin/env" 2>/dev/null || true

OUT_DIR="/Users/apple/Desktop/evocanvas/traces"
mkdir -p "$OUT_DIR"

# 公共参数：不弹浏览器、不开 live viewer
TAP_OPTS="--tap-client codex --tap-no-live --tap-no-open --tap-store-stream-events"

run_scenario() {
  local num=$1
  local prompt=$2
  local codex_args=$3
  echo ""
  echo "════════════════════════════════════════════"
  echo "  场景 $num: $4"
  echo "════════════════════════════════════════════"
  echo ""

  # 运行 claude-tap + codex
  claude-tap $TAP_OPTS -- $codex_args -p "$prompt"

  # 等待 trace 写入
  sleep 2

  # 导出最新的 trace
  echo "导出 trace → $OUT_DIR/scenario_${num}.json ..."

  # 从 SQLite 取最新一条 trace 的文件路径
  local trace_file
  trace_file=$(sqlite3 "$HOME/.local/share/claude-tap/traces.sqlite3" \
    "SELECT path FROM traces ORDER BY created_at DESC LIMIT 1;" 2>/dev/null || echo "")

  if [ -n "$trace_file" ] && [ -f "$trace_file" ]; then
    claude-tap export "$trace_file" --format json -o "$OUT_DIR/scenario_${num}.json"
    echo "✓ 场景 $num 导出完成: $OUT_DIR/scenario_${num}.json"
  else
    # fallback: 用 claude-tap dashboard 查找
    echo "⚠ 自动定位 trace 失败，请稍后用 claude-tap export 手动导出"
  fi
  echo ""
}

# ── 场景定义 ──────────────────────────────────

scenario_1() {
  run_scenario 1 \
    "你是一个产品经理助理。请分析以下混杂的产品需求输入，整理为结构化需求列表：

我们有500多个门店，每个门店有3-5个收银台。顾客结账时收银员需要手动输入会员手机号查积分，但很多顾客不愿意给手机号，导致积分使用率很低。老板说要做个电子会员卡，但没说具体怎么做。运营那边说希望能自动推送优惠券到会员手机上。技术团队说现有POS系统是3年前外包做的，没有API。另外我们小程序上已经有会员注册功能但和POS不通。

请：1) 识别所有利益相关者 2) 列出显式和隐式需求 3) 标注需求间的冲突和依赖关系" \
    "--full-auto" \
    "需求编译：混杂输入结构化"
}

scenario_2() {
  run_scenario 2 \
    "继续上一轮的需求分析。现在有以下补充信息和疑问：

1. 门店分直营和加盟两种，加盟店不愿意共享会员数据
2. POS系统虽然没有API，但可以导出每日交易CSV
3. 预算只有10万元，需要在3个月内上线第一版

基于这些新约束，请重新审视之前的需求列表：
- 哪些需求在预算和时间内不可行？
- 加盟和直营的数据隔离应该如何处理？
- 最小可行版本应该包含哪些功能？" \
    "--full-auto" \
    "多轮澄清：追加约束后重新收敛"
}

scenario_3() {
  run_scenario 3 \
    "请从以下产品讨论记录中提取所有约束条件，按技术约束、业务约束、资源约束分类：

【讨论记录】
CTO: 我们的用户数据都在阿里云RDS上，但新系统可能部署在AWS上，数据迁移是个大问题。
产品总监: 用户反馈最多的就是加载太慢，首页要3秒才出来。但设计团队坚持要用高清大图。
运营VP: Q4大促必须在11月1号前上线，不能延期，市场部已经定了推广计划。
技术负责人: 团队现在只有3个后端2个前端，还有一个下个月要休产假。现有的微服务框架太老了，新人上手要两周。
CEO: 竞品X已经上线了AI推荐功能，我们不能再落后了。但安全第一，用户隐私不能出问题。
财务: 云服务预算每月不能超过5万，超出部分需要单独审批。

请将每个约束表述为：[约束类型] 约束内容 → 对产品设计的影响" \
    "--full-auto" \
    "约束提取：从讨论中沉淀约束"
}

scenario_4() {
  run_scenario 4 \
    "请帮我写一个Python脚本，实现以下功能：

1. 读取一个CSV文件（包含产品名称、价格、库存数量列）
2. 计算每个产品的库存健康度评分（基于销量趋势和当前库存）
3. 生成一份Markdown格式的库存分析报告
4. 将报告保存为文件

要求：
- 使用标准库，不依赖第三方包
- 包含错误处理和日志
- 写完后创建示例CSV并运行测试" \
    "--full-auto" \
    "代码生成+工具调用：写代码并执行"
}

scenario_5() {
  run_scenario 5 \
    "我在做一个SaaS产品，需要设计定价策略。以下是背景：

产品是一个项目管理工具，目标用户是10-100人的创业团队。
核心功能：任务看板、甘特图、团队日历、文件共享、即时通讯。
竞品：Notion（免费+付费）、Monday.com（按人头收费）、飞书（免费为主）。

请帮我分析定价策略。

--- 第2轮 ---
我们决定用免费增值模式。免费版限制5人，付费版按月收费。请设计具体的价格梯度。

--- 第3轮 ---
考虑加入年付折扣和企业版。年付打几折合适？企业版应该比团队版多哪些功能？

--- 第4轮 ---
如果我们的获客成本(CAC)是200元，用户平均生命周期是24个月，请计算LTV/CAC比率并评估定价是否健康。

--- 第5轮 ---
现在请把所有定价决策整合为一份完整的定价方案文档，包含：价格表、功能对比矩阵、升级路径、和财务预测。" \
    "--full-auto" \
    "长对话：多轮深度讨论（定价策略）"
}

# ── 执行 ──────────────────────────────────────

if [ -z "$1" ]; then
  echo "执行全部 5 个场景..."
  scenario_1
  scenario_2
  scenario_3
  scenario_4
  scenario_5
else
  case $1 in
    1) scenario_1 ;;
    2) scenario_2 ;;
    3) scenario_3 ;;
    4) scenario_4 ;;
    5) scenario_5 ;;
    *) echo "用法: bash capture.sh [1-5]" ;;
  esac
fi

echo ""
echo "════════════════════════════════════════════"
echo "  全部采集完成！"
echo "  Trace 文件位于: $OUT_DIR/"
echo "  也可用 claude-tap dashboard 浏览所有记录"
echo "════════════════════════════════════════════"
