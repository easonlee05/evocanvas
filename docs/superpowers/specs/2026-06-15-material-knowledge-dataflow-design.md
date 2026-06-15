# EvoCanvas 1.0 资料分流、知识沉淀与数据库直连引用设计

> 状态：评审中草案
> 最后更新：2026-06-15
> 范围：EvoCanvas 1.0 输入层、知识层、产物层与外部数据引用
> 对齐基线：[docs/vision/EvoCanvas1.0-PRD.md](/Users/apple/Desktop/evocanvas/docs/vision/EvoCanvas1.0-PRD.md)

## 1. 背景

EvoCanvas 1.0 首版要验证的核心命题不是“把资料都收进系统”，而是：

`输入编译 -> 待澄清问题 -> 约束 / 待决策 -> 结构化交接物`

因此，平台虽然已经接入知识库，也不能把“上传过的所有东西”都视作知识库条目。否则会产生三个问题：

1. 把一次性项目材料和长期可复用知识混在一起，检索噪音迅速上升。
2. AI 会误把未经确认的原始输入当成稳定事实，削弱“先暴露不确定性”的产品原则。
3. 结构化交接物、决策记录与规则沉淀没有分层，后续很难追溯“原始证据”和“已确认结论”的边界。

本设计的核心目标是：

1. 明确上传资料不等于知识入库。
2. 明确平台产物不默认进入知识库。
3. 让数据库、报表、指标系统等外部结构化数据可以被直接引用，而不是要求用户手动导出再上传。

## 2. 设计结论

EvoCanvas 1.0 中，平台内信息统一分成 4 层：

1. `材料层 Material`：当前工作区的一次性输入材料。
2. `知识层 Knowledge`：跨任务可复用、经过筛选的稳定知识。
3. `产物层 Artifact/Handoff`：本次收敛过程中生成的结构化结果。
4. `数据源引用层 SourceRef`：来自数据库、报表或外部系统的结构化只读引用。

四层必须分开存储、分开治理、分开展示，不应互相偷用语义。

## 3. 为什么不能全部放进知识库

不是所有上传内容都具有“知识”属性。

以下内容默认不应直接进入知识库：

1. 会议纪要原文
2. 飞书/IM 聊天摘录
3. 用户反馈截图
4. 某次临时导出的 CSV
5. 某个项目阶段的脑暴草稿
6. 尚未确认真伪的数据摘录

这些内容对当前 workspace 很重要，但它们的角色是“输入证据”而不是“稳定知识”。

如果全部入知识库，会直接违背 EvoCanvas 1.0 的产品原则：

1. 系统应先显性化冲突与缺口，而不是先把资料包装成确定结论。
2. Todo、约束、待决策、交接物都需要回指原始来源，不能被知识库条目提前替代。
3. 知识检索应该服务于“补背景”和“复用稳定规则”，而不是成为材料堆放区。

## 4. 四层对象模型

### 4.1 材料层 Material

定义：用户为当前任务上传或接入的原始资料。

典型来源：

1. 文档片段
2. 会议纪要
3. 聊天记录
4. 截图说明
5. 用户反馈
6. 数据导出文件
7. 临时想法文本

材料层职责：

1. 为输入编译提供证据来源
2. 为卡片提供来源追溯
3. 为 AI 提供“可引用但未经确认”的原始输入

材料层不承担：

1. 长期知识复用
2. 稳定事实定义
3. 跨项目知识召回

建议字段：

- `material_id`
- `workspace_id`
- `source_type`
- `filename` 或 `display_name`
- `content_ref`
- `summary`
- `parsed_status`
- `uploaded_by`
- `uploaded_at`
- `retention_policy`
- `sensitivity_level`

### 4.2 知识层 Knowledge

定义：经过筛选后可跨任务复用的稳定背景知识。

典型内容：

1. 业务规则
2. 术语口径
3. 字段定义
4. 指标定义
5. 交付模板
6. 历史最佳实践
7. 已确认的长期约束

知识层职责：

1. 在输入编译前后补充背景上下文
2. 在澄清、约束、待决策阶段提供历史参考
3. 降低重复解释成本

知识层准入标准：

1. 对多个任务或多个 workspace 有复用价值
2. 语义相对稳定，不依赖某一次上下文才成立
3. 来源清晰，可追溯
4. 最好已有确认主体、确认方式或稳定出处

建议字段：

- `knowledge_id`
- `kind`：`doc | rule | template | metric | glossary`
- `title`
- `summary`
- `body`
- `tags`
- `source_refs`
- `status`：`candidate | approved | archived`
- `scope`：`global | team | project_line`
- `verified_by`
- `verified_at`

### 4.3 产物层 Artifact / Handoff

定义：EvoCanvas 在一次工作收敛中生成的结构化结果。

典型内容：

1. 结构化交接物
2. 快照
3. 决策记录
4. 已确认约束清单
5. 待澄清推进记录

产物层职责：

1. 记录“这次到底推进了什么”
2. 为不同 AI 或不同会话提供延续上下文
3. 保留结果与版本，而不是替代原始输入

产物层默认不直接进入知识库。

只有当产物中某部分满足知识层准入标准时，才允许“提炼入库”，并且应以抽取后的知识条目入库，而不是整份交接物原文入库。

建议字段：

- `artifact_id`
- `workspace_id`
- `artifact_type`
- `version`
- `status`
- `content_ref`
- `source_card_ids`
- `source_material_ids`
- `confirmed_by`
- `confirmed_at`
- `created_at`

### 4.4 数据源引用层 SourceRef

定义：对外部数据库、BI、报表系统、内部服务或其他结构化系统的只读引用。

它不是上传文件，也不是知识条目，而是一种“可被任务直接引用的证据入口”。

典型来源：

1. 数据库表
2. 保存好的 SQL 查询
3. BI 仪表盘
4. 指标服务
5. API 返回快照
6. CRM / 工单 / 埋点系统的结果集

建议字段：

- `source_ref_id`
- `workspace_id`
- `connector_type`
- `resource_locator`
- `query_id` 或 `query_text`
- `filters`
- `snapshot_ref`
- `schema_preview`
- `sample_rows`
- `aggregates`
- `captured_at`
- `captured_by`
- `access_scope`

## 5. 上传资料的处理原则

### 5.1 默认策略

默认情况下，上传资料先进入 `Material`，不直接进入 `Knowledge`。

处理流程建议为：

1. 上传文件或粘贴内容
2. 系统创建 `material`
3. `material.parse` 提取结构化片段、摘要和候选证据
4. 输入编译阶段基于材料生成 evidence / clarification / constraint candidate
5. 在工作推进中，只有被确认具备复用价值的部分才进入“知识候选区”

### 5.2 自动分流规则

建议增加简单而稳定的分流规则：

1. `项目一次性材料`：只进 workspace 材料区
2. `明显长期规则型内容`：允许用户勾选“同时加入知识候选”
3. `模板型文档`：允许进入知识候选，但默认仍需审核
4. `结构化数据导出`：优先建议改用数据源引用，不鼓励长期用导出文件上传

### 5.3 不要自动知识化的内容

以下内容不建议自动入知识库：

1. 未经确认的待澄清结论
2. 单次项目特有的背景描述
3. 临时版本 handoff 草稿
4. 仅对某个时间窗口成立的数据截图
5. 无清晰来源的复制粘贴内容

## 6. 产出数据的处理原则

### 6.1 默认落点

平台产出默认进入 `Artifact/Handoff`，不直接进入 `Knowledge`。

原因是：

1. 交接物首先是“当前任务的收敛结果”
2. 决策记录首先是“当前上下文中的裁决痕迹”
3. 快照首先是“某个时刻的认知视图”

它们都应先服务于任务延续与追溯，而不是立即当成全局知识。

### 6.2 哪些产物适合升格为知识

适合从产物层提炼入知识库的对象包括：

1. 多次重复出现并被确认的业务规则
2. 已确认且长期有效的约束
3. 可复用的交接模板
4. 明确稳定的术语定义
5. 通用的指标解释口径

不适合直接升格的对象包括：

1. 整份项目 handoff 原文
2. 一次性的 trade-off 讨论全文
3. 与具体时间窗口强绑定的决策
4. 某一轮未定稿的 AI 汇总

### 6.3 建议引入“知识候选区”

为避免“要么不沉淀，要么全量入库”的极端模式，建议知识库增加中间态：

- `candidate`
- `approved`
- `archived`

推荐流程：

1. 任务结束或阶段收束时，从产物中抽取候选知识
2. 进入知识候选区
3. 用户或管理员确认后转成 `approved`
4. 过时条目可进入 `archived`

这与现有 `diff.extract_rules` “只生成候选，不直接入库”的治理思路一致。

## 7. 如何直接引用数据库里的数据

### 7.1 设计原则

数据库数据不应要求用户先导出再上传。

更合理的方式是让任务引用“受控的数据快照”，而不是引用一个手工文件。

核心原则：

1. 引用的是 `SourceRef`，不是上传文件
2. AI 读取的是查询结果快照，不是整库自由漫游
3. 每次引用都必须保留查询条件、时间戳和访问范围
4. 数据引用进入 workspace 后，仍然先作为证据，而不是自动成为结论

### 7.2 推荐能力形态

建议新增一种与 `material.parse`、`knowledge.retrieve` 平行的能力：

- `source.read`
- 或 `data.retrieve`

它的职责是：

1. 按授权连接外部数据源
2. 读取指定表、查询、报表或 API 结果
3. 生成可审计的数据快照
4. 返回 schema、样本、聚合摘要与可引用片段

不建议把这类能力硬塞进 `knowledge.retrieve`，因为语义不同：

1. `knowledge.retrieve` 是找稳定背景知识
2. `source.read` 是取当前结构化证据

### 7.3 最小可用引用模型

EvoCanvas 1.0 可以先支持以下 5 类引用：

1. `saved_query`
2. `dashboard_metric`
3. `table_slice`
4. `api_snapshot`
5. `record_lookup`

每次引用返回的内容不必很重，最小可包括：

1. 数据源名称
2. 查询标识或报表标识
3. 查询条件
4. 拉取时间
5. 字段预览
6. 样本行
7. 聚合结果
8. 一段 AI 可消费的安全摘要

### 7.4 为什么必须做快照而不是实时裸连

如果让 AI 每次都实时直连数据库，会带来几个风险：

1. 同一句话在不同时间检索出不同结果，导致推理不可复现
2. 没法回溯“这条结论当时基于哪版数据”
3. 权限边界不清，AI 容易越权读到不该看的数据

因此，推荐策略是：

1. 用户选择数据源或保存查询
2. 系统生成一次只读 `snapshot`
3. 当前任务只引用该 snapshot
4. 如需刷新，显式生成新 snapshot，并保留版本差异

## 8. 1.0 推荐数据流

### 8.1 文件/文本资料流

`上传资料 -> Material -> material.parse -> evidence / clarification / constraint candidate -> handoff / artifact -> 抽取知识候选 -> 审核后入 Knowledge`

### 8.2 数据库/报表资料流

`选择数据源 -> SourceRef -> source.read -> data snapshot -> evidence card -> clarification / constraint / decision candidate -> handoff / artifact`

### 8.3 知识反哺流

`任务开始或推进时 -> knowledge.retrieve -> 召回稳定背景知识 -> 辅助编译与澄清 -> 产出新候选知识`

## 9. 前端交互建议

### 9.1 上传区不要只写“上传到知识库”

在 Workspace 中，上传入口应明确区分：

1. `添加当前资料`
2. `引用知识库条目`
3. `连接数据源`

这样用户天然知道三者不是一回事。

### 9.2 知识库页面不应承担材料收纳

知识库页面应只展示：

1. 已批准知识
2. 候选知识
3. 关系图谱
4. 来源与引用链路

不应把每个上传文件直接显示成知识节点。

### 9.3 数据引用要可视化为“带时间戳的证据卡”

当用户从数据库引用数据后，画布上更适合出现：

1. 数据证据卡
2. 查询条件摘要
3. 拉取时间
4. 数据源标识
5. 可展开的样本和聚合结果

而不是假装它是普通附件。

## 10. 后端接口演进建议

结合当前代码现状，推荐按最小增量演进：

### 10.1 保留现有能力

保留：

1. `/api/materials`
2. `material.parse`
3. `knowledge.retrieve`
4. artifact / handoff / snapshot 现有链路

### 10.2 新增能力

建议新增：

1. `GET /api/source-connectors`
2. `POST /api/source-refs`
3. `POST /api/source-refs/{id}/snapshot`
4. `GET /api/source-refs/{id}`
5. `POST /api/knowledge/candidates`
6. `POST /api/knowledge/{id}/approve`

对应工具层建议新增：

1. `source.read`
2. `knowledge.candidate.write`
3. `knowledge.candidate.approve`

### 10.3 不建议的做法

不建议：

1. 让 `/api/knowledge` 直接承担所有上传入口
2. 让 `knowledge.retrieve` 同时负责数据库直读
3. 让 handoff 全文自动入知识库
4. 让 AI 直接拿到原始数据库连接并自由查询

## 11. 治理与权限建议

### 11.1 材料层

治理重点：

1. 来源追溯
2. 敏感级别
3. 生命周期清理

### 11.2 知识层

治理重点：

1. 审核状态
2. 失效治理
3. 来源可信度

### 11.3 数据源引用层

治理重点：

1. 连接器权限边界
2. 查询白名单或保存查询
3. snapshot 审计日志
4. 行列级脱敏

## 12. 推荐的 1.0 落地顺序

如果只按 EvoCanvas 1.0 最小闭环推进，建议顺序如下：

1. 先把“上传资料默认只进 Material，不直接进 Knowledge”定成产品规则。
2. 再把“产物默认进 Artifact/Handoff，不直接进 Knowledge”定成治理规则。
3. 然后补一个“知识候选区”，承接可沉淀内容。
4. 最后新增 `source.read` / `data.retrieve`，支持数据库和报表的直接引用。

这样既不会破坏现有 `material.parse` 与 `knowledge.retrieve` 分工，也最符合 EvoCanvas 1.0 的产品主轴。

## 13. 最终结论

EvoCanvas 1.0 不应该把所有上传资料都塞进知识库。

正确做法是：

1. 原始资料进入 `Material`
2. 稳定背景进入 `Knowledge`
3. 任务结果进入 `Artifact/Handoff`
4. 外部结构化数据通过 `SourceRef + Snapshot` 直接引用

这样才能同时满足：

1. 先暴露不确定性，而不是过早知识化
2. 保留原始证据与已确认结论的边界
3. 让平台产物可追溯、可复用、但不过度污染知识库
4. 让数据库里的数据可以成为受控证据，而不是手工上传文件
