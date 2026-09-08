# EvoCanvas 历史文档隔离区

> 状态：`非现行规格，不得作为实现输入`
> 当前权威：[`EvoCanvas1.0-PRD.md`](../vision/EvoCanvas1.0-PRD.md) -> [`Harness`](../harness/README.md) -> [`Technical Specs`](../technical-specs/00%20Technical%20Baseline%EF%BC%88%E6%8A%80%E6%9C%AF%E8%90%BD%E5%9C%B0%E6%80%BB%E8%A7%88%EF%BC%89.md)

本目录只为保留迁移审计和历史设计背景。目录内文件可能包含旧产品线、阶段路由、Pi 外部 Product Kernel、独立判断/收敛运行、旧确认队列、旧状态账本、旧页面或已失效的绝对路径。

规则：

1. 本目录不计入 Harness L3、主 PRD、模块文档或现行 Technical Specs 的完整性判断。
2. 不得从本目录恢复接口、状态、对象或实现任务；需要复用时必须先回到现行权威文档重新核对。
3. 本目录内链接、日期、代码路径和实现结论按历史原貌保留，不承诺当前可用。
4. 新的现行规格不得写入本目录；新的历史材料也不应默认新增，除非迁移审计确有需要。

已隔离内容：

- `technical-specs/`：旧 L / G / V 运行时与前端快照；
- `plans/`：已被 Pi 核心目标架构取代的执行设计；
- `prompt-engineering/`：旧阶段 Prompt 横切方案；
- `superpowers/`：旧页面、后端、自由画布和 Agent Team 设计/计划。
