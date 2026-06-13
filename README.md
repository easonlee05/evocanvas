# EvoCanvas

EvoCanvas 是一个面向产品经理的对话驱动工作台。

这个仓库不是从零重写，而是**在 Evoloop 现有基础设施之上进行半重构迁移**：

- 复用通用前端骨架与 Workspace 交互壳
- 复用后端任务、事件、工具、会话、MCP、CLI 等基础设施
- 逐步移除旧 `manual / prd / Evoloop 工作台` 产品语义
- 收敛到新的 `EvoCanvas 1.0` 产品方向

## 当前产品目标

EvoCanvas 不是 PRD 生成器，也不是自由白板工具。当前产品主线是：

- 承接多源混杂输入
- 暴露待澄清问题、冲突信息和待决策事项
- 沉淀约束与边界
- 收束出可供人或 AI 继续推进的结构化交接物

当前仓库对齐 `EvoCanvas 1.0` 首版方向。首版只验证最小闭环：

`输入编译 -> 待澄清问题 -> 约束 / 待决策 -> 结构化交接物`

## 迁移策略

本仓库当前采用“半重构迁移”策略：

1. **保留可复用底座**
   - `app/core`
   - `app/services`
   - `app/api`
   - `app/mcp`
   - `app/cli`
   - 通用 workflow/runtime 基础设施
   - 前端通用组件与 Workspace 工作台壳
2. **剥离旧产品面**
   - 旧任务大厅、知识库、法则审核、回收站、沙盒等 EvoLoop 产品页面
   - 明显服务于 `manual / prd / spec_to_agent / acceptance_review` 的旧产品线语义
3. **逐步替换旧实现**
   - 把旧命名、旧文案、旧交互逐步替换为 EvoCanvas 语义
   - 在复用底座的同时，逐步抽离出新的产品对象模型和流程

## 当前目录

```text
app/                  # 从 Evoloop 迁移来的可复用后端基础设施
frontend/             # 从 Evoloop 迁移来的前端基础壳与 EvoCanvas 页面
tests/                # 可复用基础设施测试
reference/            # 暂未纳入主路径、但后续可能继续复用的旧后端代码与测试参考
docs/
  vision/
    EvoCanvas1.0-PRD.md
```

## 文档入口

优先阅读：

```text
docs/vision/EvoCanvas1.0-PRD.md
AGENTS.md
```

其中已经明确：

- `1.0` 首版验证命题
- `1.0` 范围与后续路线图
- 核心对象：待澄清、约束、待决策、交接物
- AI 协作协议与验收标准

`reference/` 目录中的内容仅作为迁移参考：

- 不默认参与当前主路径实现
- 不作为首版产品真相源
- 仅用于后续重构时复用旧后端能力、对照历史实现或迁移测试

## 本地运行

前端：

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

后端：

```bash
python3 -m uvicorn app.api.server:app --host 127.0.0.1 --port 8000 --reload
```

前端如需连接后端，可通过环境变量覆盖：

```bash
VITE_API_BASE=http://127.0.0.1:8000 npm --prefix frontend run dev
```

## 产品路线

- `1.0`：把多源输入收敛成可交接上下文
- `2.0`：把上下文继续收束成可执行方案
- `3.0`：让多角色围绕结构化对象协作
- `4.0`：把协作结果继续编排到交付链路
