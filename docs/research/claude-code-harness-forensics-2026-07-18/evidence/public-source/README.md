# 公开非官方源码快照证据

## 来源定性

检查对象：<https://github.com/fyu/claude-code>

固定 commit：

```text
642c7f944bbe5f7e57c05d756ab7fa7c9c5035cc
```

仓库 README 明确表示它不是 Anthropic 官方仓库，并称内容来自 `@anthropic-ai/claude-code v2.1.88` 的 source map。报告因此把它定为：

```text
unofficial source-map extraction / structural navigation only
```

## 本目录保存什么

- `source-snapshot-manifest.json`：remote、commit、日期、文件数和选择文件 SHA-256。
- `source-symbol-index.json`：关键符号所在文件、行号、匹配次数和文件 SHA-256。
- `deep-control-flow-index.json`：query loop、streaming tool execution、权限/Hook、Context、Session、Compaction 与 Subagent 的行号级控制流索引。
- `source-tree.txt`：`src/` 一级目录结构。

## 为什么不复制完整源码

本研究只需要证明 `queryLoop`、上下文装配、工具并发分类、Pre/Post Hook 和 autoCompact 等结构存在。保存指纹和符号位置已经足以复核，不需要把非官方提取的完整专有源码再次提交到 EvoCanvas。
