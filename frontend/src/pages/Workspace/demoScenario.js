/**
 * @file demoScenario.js
 * @description EvoCanvas 1.0 演示工作台的统一场景定义，确保对话、画布与交接物讲述同一条收敛链路。
 */

export const PLACEHOLDER_NAMES = ['张三', '李四', '王五', '赵六', '测试用户'];

export const DEMO_PROJECT_TITLE = '618 会员积分防刷治理一期';

export const DEMO_CHAT = [
  {
    id: 'm1',
    role: 'ai',
    text:
      '我已经完成这轮输入编译，当前汇入了客服投诉摘录、活动日报、竞品策略笔记和研发评估四类材料。先不急着给方案，画布里已经显性化了三个高风险缺口和两条必须确认的约束。',
  },
  {
    id: 'm2',
    role: 'user',
    text:
      '先帮我收束问题，不要直接写方案。我想先知道这次 618 积分防刷到底在解决什么。',
  },
  {
    id: 'm3',
    role: 'ai',
    text:
      '目前可以确认的核心问题有两层：\n\n- 活动高峰期存在批量刷分行为，投诉和异常积分回补同时上升\n- 现有发放链路缺少统一的高风险识别口径，导致运营、客服、研发对“该拦什么”理解不一致\n\n我已经把这些证据映射到“探索发现”和“需求定义”两列。',
  },
  {
    id: 'm4',
    role: 'ai',
    text:
      '已在画布新增 3 张证据卡，分别对应客服反馈、活动日报和竞品参考。每张卡都保留了来源、摘要和可追溯细节，方便后面继续追问而不是直接跳结论。',
  },
  {
    id: 'm5',
    role: 'user',
    text:
      '那先把待澄清问题列出来，尤其是一期范围和误杀成本，别让 AI 自己脑补。',
  },
  {
    id: 'm6',
    role: 'ai',
    text:
      '已补充三类待澄清项：\n\n1. 高风险账号到底按账号、设备还是行为会话聚合\n2. 误杀后申诉 SLA 由谁兜底，客服是否有人工放行权限\n3. 618 活动窗口内是否允许先做规则拦截、后补模型识别\n\n同时我把“结算中心不可改”“P95 额外耗时不超过 120ms”沉淀成了明确约束。',
  },
  {
    id: 'm7',
    role: 'user',
    text:
      '可以，一期先聚焦邀请返积分和签到补签，不碰全站任务体系。你把需要我拍板的决策也单列出来。',
  },
  {
    id: 'm8',
    role: 'ai',
    text:
      '收到。我已在画布新增“一期范围只治理两条高风险积分任务”这张确认卡，并把“规则优先还是模型优先”“申诉回滚入口归属”两项内容放进决策确认区，避免它们继续混在讨论里。',
  },
  {
    id: 'm9',
    role: 'ai',
    text:
      '目前画布上的状态是：\n\n- 证据已经齐全，可以支撑问题定义\n- 待澄清问题还剩 3 项，需要分别找安全、设计、客服确认\n- 已确认约束有 3 条，其中范围约束已经稳定\n- 待决策项有 2 条，均需要产品负责人拍板',
  },
  {
    id: 'm10',
    role: 'user',
    text:
      '客服这边我来拍板，申诉回滚入口走客服后台，活动期要求当天闭环。你把执行项也补上，别停在结论层。',
  },
  {
    id: 'm11',
    role: 'ai',
    text:
      '好的，我已在画布新增 3 张执行卡，分别对应规则口径与埋点字段、拦截提示与申诉流程设计、活动期灰度与升级演练。这样从输入编译到执行闭环已经完整串起来了。',
  },
  {
    id: 'm12',
    role: 'ai',
    text:
      '结构化交接物也同步刷新了：现在里面已经明确写清待澄清问题、约束、待决策、建议方案和研发 / 设计 / 客服各自的接力内容。后续如果要继续演示，我可以直接基于这份上下文往下推进。',
  },
];

export const DEMO_DOC = `# 结构化交接物：618 会员积分防刷治理一期

## 当前目标

- 在不改造结算中心的前提下，先收敛 618 活动期间最容易被利用的积分发放链路
- 优先降低邀请返积分与签到补签两类任务的批量刷分风险
- 让产品、研发、客服对“一期到底拦什么、怎么申诉、哪些点必须拍板”形成统一上下文

## 输入编译结果

### 已汇入输入

- 客服投诉摘录：近 7 天用户集中反馈积分到账异常、封禁解释不清
- 活动日报：异常发放峰值出现在晚高峰，集中于邀请返积分与签到补签
- 竞品策略笔记：头部产品优先使用规则拦截，再逐步引入模型评分
- 研发评估：现有任务引擎可插入轻量校验，但结算中心本期不能改

### 已显性化冲突

- 运营希望快速止损，但客服担心误杀后没有人工兜底
- 安全策略组希望统一高风险口径，但研发提醒实时链路延迟预算有限

## 待澄清问题

1. 高风险判定口径按账号、设备还是行为会话聚合
2. 误杀申诉是否进入客服后台，以及人工放行 SLA 由谁负责
3. 活动窗口期是否允许先上线规则拦截，模型识别延后到二期

## 已确认约束

- 结算中心本期不做结构改造
- 风险校验新增链路的 P95 额外耗时不超过 120ms
- 一期范围只覆盖邀请返积分与签到补签，不扩展到全站任务体系

## 待决策项

1. 是否先采用规则拦截方案，再补模型评分
2. 申诉回滚入口放在客服后台还是运营后台
3. 误杀复核是否要求 T+0 完成

## 当前建议方案

- 一期先落地规则拦截、设备指纹复用和人工申诉兜底
- 把“高风险命中解释”和“申诉结果回写”作为必须交付项，避免客服无法对外说明
- 模型评分、跨活动全局画像和复杂策略编排统一放入二期

## 交接给研发 / 设计 / 客服的内容

### 研发

- 风险校验插入点
- 规则优先级与兜底逻辑
- 命中日志字段与申诉回写接口

### 设计

- 风险拦截提示文案
- 申诉入口状态与结果反馈
- 客服后台的复核信息结构

### 客服与运营

- 可解释口径
- 人工放行边界
- 活动期间升级路径
`;

export const DEMO_DOC_SECONDARY = `# 画布快照说明

## 本次演示如何走完 EvoCanvas 1.0 最小闭环

1. 先做输入编译，把投诉、日报、竞品和研发评估放进同一张工作面
2. 再把冲突和缺口显性化，优先沉淀待澄清问题与约束
3. 再把必须由产品负责人拍板的事项单列为待决策
4. 最后从当前画布收束出结构化交接物，供研发、设计与客服继续推进

## 这张画布当前强调什么

- 左侧是证据，不是假结论
- 中间先暴露不确定性，而不是抢先定方案
- 右侧只放已确认约束和待拍板决策
- 最后一列是最小执行闭环，不扩展成完整任务系统
`;

export const DEMO_CANVAS_SECTIONS = {
  evidence: [
    {
      id: 'e1',
      title: '活动高峰期刷分投诉与异常补发同时上升',
      desc: '客服在 7 天内累计收到 47 条相关投诉，用户核心抱怨不是“没拿到积分”，而是“规则不透明、被拦后没人解释”。',
      structureKind: 'quote',
      structuredItems: ['异常集中在晚 8 点到 11 点', '邀请返积分与签到补签占投诉量的 81%'],
      confidence: 84,
      source: { label: '来源', name: '王静宜 · 客服经理', avatar: '王', avatarTone: 'violet' },
      tags: [
        { label: '用户反馈', color: 'red' },
        { label: '高风险', color: 'yellow' },
      ],
      next: 'p1',
    },
    {
      id: 'e2',
      title: '活动日报显示异常积分峰值与设备复用高度重叠',
      desc: '数据侧抽样发现同一设备指纹在 2 小时内触发了多账号积分领取，说明当前发放链路缺少实时拦截能力。',
      structureKind: 'quote',
      structuredItems: ['异常峰值时段发放量较日常增长 3.6 倍', 'Top 20 设备指纹贡献了 38% 的可疑领取'],
      confidence: 92,
      source: { label: '来源', name: '周岚 · 数据分析师', avatar: '周', avatarTone: 'teal' },
      tags: [
        { label: '数据证据', color: 'blue' },
        { label: '异常峰值', color: 'yellow' },
      ],
      next: 'p1',
    },
    {
      id: 'e3',
      title: '竞品先用规则止损，再逐步叠加模型识别',
      desc: '竞品案例显示，先把高风险任务链路收窄，再补模型评分，更容易在活动窗口期兼顾止损速度和误杀控制。',
      structureKind: 'quote',
      structuredItems: ['一期只治理最易被利用的任务', '客服侧必须能看到命中原因与申诉状态'],
      confidence: 76,
      source: { label: '来源', name: '林奕辰 · 竞品研究', avatar: '林', avatarTone: 'amber' },
      tags: [
        { label: '外部参考', color: 'gray' },
        { label: '策略借鉴', color: 'blue' },
      ],
      next: 'p1',
    },
  ],
  problems: [
    {
      id: 'p1',
      title: '618 积分发放链路治理（v1.0）',
      desc: '先把一期要治理的任务边界、校验插入点和误杀兜底方式收敛清楚，避免又回到“大而全”的反作弊改造。',
      structureKind: 'list',
      structuredItems: ['目标是快速止损，而不是一次做完整风控平台', '对象是邀请返积分与签到补签两条链路'],
      statusPill: { label: '范围已聚焦', color: 'blue' },
      owner: { label: '负责人', name: '陈嘉木 · 产品经理', avatar: '陈', avatarTone: 'slate' },
      attachments: [
        { icon: '🧾', label: '输入编译摘要' },
        { icon: '🗺️', label: '链路草图' },
      ],
      next: ['c1', 'c2', 'r1'],
    },
    {
      id: 'p2',
      title: '申诉回滚与人工复核流程',
      desc: '如果只拦截不解释，客服会立刻承压，所以必须在一期明确申诉入口、回滚边界和结果回写方式。',
      structureKind: 'list',
      structuredItems: ['客服是否有人工放行权限', '申诉结果是否回写运营看板'],
      statusPill: { label: '需要拍板', color: 'yellow' },
      owner: { label: '协同方', name: '沈清和 · 客服运营负责人', avatar: '沈', avatarTone: 'rose' },
      attachments: [{ icon: '📄', label: '申诉流程草案' }],
      next: ['c3', 'r2'],
    },
  ],
  clarify: [
    {
      id: 'c1',
      title: '高风险口径按什么维度聚合',
      desc: '安全策略组倾向于设备 + 行为会话联合判定，但研发担心实时计算超预算，需要先收敛一期最小实现口径。',
      structureKind: 'list',
      structuredItems: ['账号维度实现最快，但绕过成本低', '设备维度收益高，但要确认指纹服务稳定性'],
      statusPill: { label: '待澄清', color: 'yellow' },
      owner: { label: '待确认', name: '贺知行 · 安全策略负责人', avatar: '贺', avatarTone: 'emerald' },
      next: 'r1',
    },
    {
      id: 'c2',
      title: '规则拦截后的误杀解释怎么对外呈现',
      desc: '如果命中后只显示“领取失败”，用户会重复投诉；需要确认前台提示文案和客服可见解释口径是否同步设计。',
      structureKind: 'list',
      structuredItems: ['前台提示是否直接暴露风险原因', '客服后台是否展示命中规则名称'],
      statusPill: { label: '待澄清', color: 'yellow' },
      owner: { label: '待确认', name: '许书瑶 · 体验设计师', avatar: '许', avatarTone: 'orange' },
      next: 'r2',
    },
    {
      id: 'c3',
      title: '申诉 SLA 由谁兜底，是否要求 T+0 完成',
      desc: '客服希望活动期内当天闭环，运营担心人工成本上升，需要结合投诉峰值与人力班次做最终拍板。',
      structureKind: 'list',
      structuredItems: ['若不承诺 T+0，需补充用户预期管理文案', '若承诺 T+0，必须明确升级路径'],
      statusPill: { label: '待决策前置', color: 'yellow' },
      owner: { label: '待确认', name: '沈清和 · 客服运营负责人', avatar: '沈', avatarTone: 'rose' },
      next: 'r3',
    },
  ],
  rules: [
    {
      id: 'r1',
      title: '一期范围只治理两条高风险积分任务',
      desc: '确认邀请返积分与签到补签为一期唯一治理对象，其他任务保持观察，不在本轮需求中扩散。',
      structureKind: 'checkpoints',
      structuredItems: [
        { text: '一期方案：上线规则拦截与提示策略，覆盖高频风险场景。', state: 'done' },
        { text: '二期方案：接入模型评分，优化误拦率并提升召回能力。', state: 'pending' },
      ],
      statusPill: { label: '已确认', color: 'green' },
      owner: { label: '拍板人', name: '陈嘉木 · 产品经理', avatar: '陈', avatarTone: 'slate' },
      next: 'd1',
    },
    {
      id: 'r2',
      title: '先上规则拦截，模型评分延后到二期',
      desc: '当前活动窗口优先要速度与可解释性，因此采用规则优先策略，并要求每次拦截都能回溯命中原因。',
      structureKind: 'checkpoints',
      structuredItems: [
        { text: '一期方案：实时链路先复用设备指纹与频次规则。', state: 'done' },
        { text: '二期方案：模型评分进入活动后复盘，不阻塞一期上线。', state: 'pending' },
      ],
      statusPill: { label: '待审批', color: 'yellow' },
      owner: { label: '审批中', name: '贺知行 · 安全策略负责人', avatar: '贺', avatarTone: 'emerald' },
      next: 'd2',
    },
    {
      id: 'r3',
      title: '申诉回滚入口进入客服后台，活动期承诺 T+0 复核',
      desc: '误杀不是附属问题，而是一期是否能稳定运行的关键，因此申诉入口和客服回写要随主链路一起交付。',
      structureKind: 'checkpoints',
      structuredItems: [
        { text: '客服后台展示命中原因、处理状态和回滚结果。', state: 'done' },
        { text: '当日未闭环必须自动升级到运营值班群。', state: 'done' },
      ],
      statusPill: { label: '已审批', color: 'green' },
      owner: { label: '负责人', name: '沈清和 · 客服运营负责人', avatar: '沈', avatarTone: 'rose' },
      next: 'd3',
    },
  ],
  planning: [
    {
      id: 'd1',
      title: '补齐高风险规则口径与埋点字段',
      desc: '研发与安全策略组共同确认一期规则清单、命中日志字段和前后台需要透出的解释信息。',
      structureKind: 'checkpoints',
      structuredItems: [
        { text: '输出规则表与字段字典', state: 'done', date: '05-08' },
        { text: '确认设备指纹服务的调用兜底', state: 'current', date: '05-11' },
      ],
      statusPill: { label: '本周启动', color: 'blue' },
      owner: { label: '执行人', name: '顾行舟 · 服务端负责人', avatar: '顾', avatarTone: 'sky' },
    },
    {
      id: 'd2',
      title: '完成拦截提示与申诉流程设计',
      desc: '把前台提示、申诉入口、客服复核视图和回滚状态反馈一次性对齐，减少上线前反复返工。',
      structureKind: 'checkpoints',
      structuredItems: [
        { text: '拦截提示文案与规则映射设计', state: 'done', date: '05-12' },
        { text: '申诉流程与页面线框设计', state: 'done', date: '05-16' },
        { text: '内部评审与合规检查', state: 'current', date: '05-20' },
        { text: '开发联调与灰度准备', state: 'pending', date: '05-24' },
      ],
      statusPill: { label: '设计排期中', color: 'gray' },
      owner: { label: '执行人', name: '许书瑶 · 体验设计师', avatar: '许', avatarTone: 'orange' },
    },
    {
      id: 'd3',
      title: '活动期灰度与客服升级机制演练',
      desc: '上线前先演练误杀申诉、人工放行和运营升级路径，确保活动窗口期出现异常时有人接、有人判、有人回写。',
      structureKind: 'checkpoints',
      structuredItems: [
        { text: '灰度首日只放 10% 流量', state: 'done', date: '05-18' },
        { text: '准备客服 FAQ 与值班升级通讯录', state: 'current', date: '05-21' },
      ],
      statusPill: { label: '待演练', color: 'yellow' },
      owner: { label: '执行人', name: '沈清和 · 客服运营负责人', avatar: '沈', avatarTone: 'rose' },
    },
  ],
};
