# 本机 Claude Runtime 证据

## 包含内容

- `claude-version.json`：当前入口版本输出。
- `claude-help.json`：公开 CLI 参数。
- `claude-agents-help.json`：Agent 子命令帮助。
- `claude-mcp-help.json`：MCP 子命令帮助；没有执行 list/get。
- `claude-auto-mode-help.json`：Auto mode 帮助；没有执行分类器检查。
- `package-metadata.json`：npm package 中与分析相关的非敏感字段。
- `local-runtime-manifest.json`：bundle、package.json、sdk types 的路径、大小、时间和 SHA-256。
- `bundle-symbol-evidence.json`：关键 Harness 字符串的出现次数。

## 证据边界

- 完整 `cli.js` 和 `sdk-tools.d.ts` 没有复制到仓库。
- 字符串计数只证明所检查 bundle 中存在对应机制名称，不证明精确调用顺序或稳定 API。
- 当前入口为 2.1.112，但 Session 清单显示其他版本元数据；不要把本目录解释为整台机器唯一 Claude 版本。

