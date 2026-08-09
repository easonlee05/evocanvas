# 复核与重建方法

## 1. 先验证证据包自身

```bash
cd /Users/apple/Desktop/evocanvas/docs/research/claude-code-harness-forensics-2026-07-18
shasum -a 256 -c SHA256SUMS
```

`MANIFEST.json` 和 `SHA256SUMS` 本身不参与 `SHA256SUMS` 的递归校验，避免循环依赖。

## 2. 重新采集本机证据

```bash
cd /Users/apple/Desktop/evocanvas
PYTHONDONTWRITEBYTECODE=1 python3 docs/research/claude-code-harness-forensics-2026-07-18/scripts/collect_evidence.py
```

脚本不会调用以下可能扩展信任范围的命令：

- `claude doctor`
- `claude mcp list/get`
- 插件列表或插件同步
- `claude auth status`
- 任何会启动项目 `.mcp.json` 中 stdio server 的命令

## 3. 手工复核本机入口

```bash
command -v claude
readlink /usr/local/bin/claude
claude --version
claude --help
shasum -a 256 /usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js
```

只应把结果解释为“被检查入口的当前状态”。本机 session 可能由其他版本或其他安装通道生成。

## 4. 重建公开源码快照

本证据包没有重新分发完整提取源码。需要复核时可自行克隆：

```bash
git clone --depth 1 https://github.com/fyu/claude-code.git /tmp/evocanvas-claude-code-2.1.88-repro
git -C /tmp/evocanvas-claude-code-2.1.88-repro rev-parse HEAD
git -C /tmp/evocanvas-claude-code-2.1.88-repro remote -v
```

预期检查 commit：

```text
642c7f944bbe5f7e57c05d756ab7fa7c9c5035cc
```

若仓库 HEAD 已变化，应 checkout 该 commit，或把新 commit 作为独立证据版本，不覆盖现有结论。

## 5. 复核 Session 摘录

查看 Session/rollout manifest：

```bash
jq '.' evidence/sessions/sanitized-session-manifest.json
jq '.' evidence/sessions/claude-session-inventory.json
jq '.' evidence/sessions/convergence-process-index.json
jq '.' evidence/sessions/desktop-session-topology.json
jq '.' evidence/public-source/deep-control-flow-index.json
```

逐行检查脱敏 JSONL 是否有效：

```bash
for session_file in evidence/sessions/*.jsonl; do
  jq -e . "$session_file" >/dev/null
done
```

原始文件绝对路径和 SHA-256 位于 manifest。若要对照原始文件，应在本机授权范围内单独查看，不要把原始 session 直接提交到仓库。

目标收敛 session 的前 289 条可用以下命令校验：

```bash
head -n 289 /Users/apple/.claude/projects/-Users-apple-Desktop-evocanvas/0eef04e9-7dcc-46f3-8f0b-8833dca85fdd.jsonl | shasum -a 256
head -n 289 /Users/apple/.claude/projects/-Users-apple-Desktop-evocanvas/0eef04e9-7dcc-46f3-8f0b-8833dca85fdd.jsonl | wc -c
```

本次固定值为 SHA-256 `0a6cc64d8e37279ac647df1f4f3631ecb1f0635527340bea94d0ae8aa6566f16`、1,156,005 bytes。

## 6. 复核工作区行号

```bash
jq '.' evidence/workspace/workspace-evidence-index.json
sed -n '1242,1268p' /Users/apple/Desktop/evocanvas/docs/vision/EvoCanvas1.0-PRD.md
sed -n '69,116p' '/Users/apple/Desktop/evocanvas/docs/harness/02-memory-state/02 State Ledger（状态账本）.md'
sed -n '66,81p' '/Users/apple/Desktop/evocanvas/docs/harness/05-safety-governance/05 Object Governance（对象治理）.md'
```

如果文件 SHA-256 与 index 不一致，应重新运行收集脚本，不能继续使用旧行号作为当前证据。

## 7. 复核原则

1. 官方文档优先用于公开能力和稳定边界。
2. 本机 bundle 优先用于当前入口的存在性验证。
3. 非官方源码快照只用于解释控制流，不用于声明当前内部 API。
4. Session 证明现场，不证明产品正确性。
5. EvoCanvas 产品判断以当前主 PRD 为真相源；Harness 与代码冲突必须显式处理。
