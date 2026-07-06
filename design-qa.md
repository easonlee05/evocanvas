# EvoCanvas 卡片 UI Kit 对照 QA

source visual truth path: `/var/folders/sr/zxfxj02x4p3d92vzd6lt9ysw0000gn/T/codex-clipboard-a11da123-1e07-4ce3-86a8-94491045ad6a.png`

implementation screenshot path: `/Users/apple/.codex/worktrees/b5db/evocanvas/tmp-evocanvas-current-cards-v2.png`

viewport: `1536x900`

state: `/workspace/demo`，默认工作台状态，右侧助手面板打开。

full-view comparison evidence: `/Users/apple/.codex/worktrees/b5db/evocanvas/tmp-evocanvas-ui-kit-comparison.png`

focused region comparison evidence: 已聚焦对比 UI Kit 顶部“01 卡片类型”与当前工作台左侧证据卡、焦点问题卡。最终 v3 截图因系统拒绝非沙箱 Chrome 截图调用未能重新捕获。

## Findings

- [P1] 第一版卡片没有贴住 UI Kit 的手绘线框语言  
  Evidence: UI Kit 使用黑色细轮廓、轻微不规则圆角、几乎无阴影、内容内框和紧凑底栏；第一版实现偏暖白 SaaS 纸卡、渐变和阴影较明显。  
  Fix: 已将 `.canvas-card` 改为白底、黑色 1.5px 手绘感边框、极轻 offset 线、低阴影；结构化内容改为单个内框列表。

- [P1] 卡片顶部信息结构偏离 UI Kit  
  Evidence: UI Kit 顶部是类型 icon、标题和更多操作，状态 badge 轻量出现；第一版用普通 chip 语义表达，图标不够像 UI Kit。  
  Fix: 已将类型 chip 改为线框 icon + 手写感标签，并按问题、待澄清、决策、约束、交接、证据映射状态色。

- [P2] 底栏不像 UI Kit 的紧凑元信息区  
  Evidence: UI Kit 底栏以图标计数、头像、姓名、进度或页码为主；第一版展示了“来源 / 负责人”等系统字段标签。  
  Fix: 已新增附件数、结构项数的轻底栏，隐藏底栏系统字段标签，仅保留头像和人名。

- [P2] 业务长内容导致卡片高度大于 UI Kit 样例  
  Evidence: UI Kit 样例多为短句和 2-3 条列表；demo 真实业务卡片摘要更长，且有来源、附件、置信度。  
  Fix: 已将标题单行、摘要两行、quote 多项内容合并到一个内框中。剩余高度差属于真实内容密度问题，后续可通过 S/M/L 卡片尺寸策略继续收敛。

## Patches Made Since Previous QA Pass

- `frontend/src/pages/Workspace/Canvas.jsx`
  - quote 结构改为单个内框列表。
  - 增加底栏附件数和结构项数。
  - 保留类型 icon、状态、标题、正文、附件、元信息和置信度结构。

- `frontend/src/pages/Workspace/Canvas.css`
  - 卡面改为 UI Kit 式黑色手绘轮廓、轻 offset 线和低阴影。
  - 背景点阵更轻、更接近 UI Kit。
  - 标签、状态、头像、附件、进度条和内容内框统一为手绘线框风格。
  - 证据 / 待澄清使用蓝色，问题使用红色，决策使用橙色，约束使用绿色，交接使用紫色。

- `frontend/src/components/common/Card.jsx`
  - 更新注释，移除旧玻璃拟态作为默认语义。

- `frontend/src/components/common/card.css`
  - 通用卡片改为更轻的纸面容器。

## Verification

- `npm --prefix frontend run build`: passed.
- `git diff --check`: passed.
- 最终视觉截图：blocked，系统拒绝再次执行非沙箱 Chrome 截图调用。

final result: blocked
