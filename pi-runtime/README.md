# Pi Runtime 当前实现与验证

生产画布回合由 `submissions → turns → Primary Pi Session → workspace.propose / workspace.commit → Revision → Canvas` 驱动。Python 不再调用旧 Supervisor 生成生产聊天提案；旧 Chat/Judgement/Convergence 合同保留用于兼容，不作为这条主链的调度器。

## 运行

要求 Node.js >= 22.19。Pi 同族依赖统一为 0.85.1。

```bash
npm --prefix pi-runtime ci
npm --prefix pi-runtime run build
npm --prefix pi-runtime start
```

通过 `PI_PROVIDER`、`PI_MODEL` 和相应 Provider 凭证配置模型；使用 `PI_RUNTIME_INTERNAL_SECRET` 配置私有接口鉴权。没有凭证或 Runtime 断连会明确失败，不伪造消息、提交或删除成功。`PI_STORAGE_DIR` 指定存储目录；默认是运行目录下的 `.pi-storage`。Python 的 `PI_RUNTIME_URL` 必须指向该服务。

## 当前主链

- `POST /v1/workspaces/:id/submissions` 保存原始 User Entry，按入口 ID 和实际内容哈希去重。
- `POST /v1/workspaces/:id/turns` 读取同一 Session 的真实消息，调用 Pi Agent，持久化 Assistant 和 Tool Result Entry。附件保存在 Session，按来源 ID 读取；上下文快照仅在模型调用时装配。
- `workspace.propose` 只产生 Session 候选；最终 Assistant Entry 附带确定性预览。`workspace.commit` 只提交用户已确认的上一组候选，确认绑定 User Entry、Actor、完整操作内容及基础 Revision。
- `POST /v1/workspaces/:id/edits` 承接用户画布直接编辑，与 Pi 工具共用提交器；稳定卡片修订仍需通过对话确认。
- Revision、当前版本指针、按工作区隔离的幂等回执在同一 SQLite 事务内写入。重启后的相同请求返回原回执，过期版本及同键不同内容明确拒绝。
- 画布和消息仓储是可重建兼容缓存。交接正文由已确认 Revision 派生，过时或失效交接不再作为默认输出。
- Python 按租户隔离 Runtime 工作区键，避免不同租户的同名工作区共享 Session。

## 验证

```bash
npm --prefix pi-runtime test
.venv/bin/python -m pytest tests/test_pi_workspace_http.py -q
```

跨语言测试只替换 Provider 的模型响应；HTTP、Python 客户端、Pi Agent、Session、Revision 和 FastAPI 画布编辑均真实执行。覆盖候选/确认、连续两次提交、幂等重试、投影重建、手工编辑、交接读取与断连失败。另有事务并发、确认伪造与 Session 重启测试。

`tests/test_canvas_turn_flow.py` 显式使用测试内的旧领域适配器，保留迁移兼容覆盖，不代表新生产主链已跑通。

## 仍需明确的迁移与验证边界

- 原有 JSON Revision 在启动时迁入事务库，原文件保留；旧 Python 工作区若存在尚未迁入 Revision 的卡片，返回 `workspace.migration_required` 并保留数据，不静默覆盖。旧工作区的数据迁移需单独核对来源和确认记录。
- 单个 Session 仅支持一个 Runtime 宿主写者；未实现跨宿主路由。进程中断后若已存在未完成的 Agent 消息，返回 `runtime.resume_unsupported`，不盲目重放未知工具效果。
- 当前工具循环由 Pi Agent 驱动，尚未接入完整 AgentHarness 的压缩、Steering 和 Deferred 恢复能力。旧运行接口的取消能力不等于新 Session 已支持全部取消与恢复入口。
- 自动化测试使用可控 Provider。真实 Provider 凭证、真实模型输出质量与浏览器人工体验需在实际配置环境中验证；测试通过不代表所有 Harness L3 能力已实现。
