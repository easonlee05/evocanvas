/**
 * @file handoffExport.js
 * @description EvoCanvas 1.0 结构化交接物视图规范化与面向 AI 的 PRD 派生工具。
 * 严格遵循主 PRD 约束：区分已确认稳定对象与仍未决边界，不把未决项伪装成结论；
 * 仅已确认交接版本允许显式发布到项目知识库。
 */

const OUTDATED_STATUSES = new Set([
  'outdated',
  'stale',
  'suspended',
  'invalidated',
  'superseded',
]);

const CONFIRMED_STATUSES = new Set([
  'confirmed',
  'formal',
  'ready',
  'approved',
]);

const PENDING_STATUSES = new Set([
  'pending_confirmation',
  'pending',
  'awaiting_confirmation',
]);

const STATUS_META = {
  draft: { label: '草稿中', tone: 'draft' },
  pending_confirmation: { label: '待确认', tone: 'pending' },
  confirmed: { label: '已确认', tone: 'confirmed' },
  outdated: { label: '已过时', tone: 'outdated' },
};

/**
 * 规范化后端/Pi Runtime 返回的交接物响应，统一映射到 1.0 四态：
 * draft | pending_confirmation | confirmed | outdated
 *
 * @param {Object | null} handoffResponse
 * @param {Array<Object>} [cards]
 */
export function normalizeHandoffView(handoffResponse, cards = []) {
  const handoff = handoffResponse?.handoff || handoffResponse || {};
  const rawStatus = String(
    handoffResponse?.status
      || handoff.status
      || handoff.governance_status
      || 'draft',
  ).toLowerCase();

  let status = 'draft';
  if (OUTDATED_STATUSES.has(rawStatus) || handoff.is_stale === true || handoffResponse?.is_stale === true) {
    status = 'outdated';
  } else if (CONFIRMED_STATUSES.has(rawStatus)) {
    status = 'confirmed';
  } else if (PENDING_STATUSES.has(rawStatus)) {
    status = 'pending_confirmation';
  }

  const meta = STATUS_META[status];
  const revisionId = handoff.revision_id
    || handoff.source_revision_id
    || handoffResponse?.revision_id
    || handoffResponse?.current_revision_id
    || '';
  const versionLabel = handoff.version_label
    || (handoff.version ? `v${handoff.version}` : '')
    || (revisionId ? revisionId.slice(0, 12) : '当前草稿');
  const staleReason = handoff.stale_reason
    || handoff.invalidation_reason
    || handoffResponse?.stale_reason
    || (status === 'outdated' ? '底层约束、决策或来源已变更，建议刷新交接草稿后重新确认。' : '');

  const summary = String(
    handoff.summary
      || handoffResponse?.content
      || '',
  ).trim();

  const cardList = Array.isArray(cards) ? cards : [];
  const openGapCount = cardList.filter((card) => {
    const kind = String(card?.kind || '').toLowerCase();
    const cardStatus = String(card?.status || '').toLowerCase();
    if (kind === 'clarification') {
      return !['resolved', 'answered', 'closed', 'archived', 'superseded'].includes(cardStatus);
    }
    if (kind === 'decision') {
      return ['pending', 'open', 'draft', 'candidate', 'pending_decision'].includes(cardStatus);
    }
    return false;
  }).length;

  return {
    status,
    statusLabel: meta.label,
    statusTone: meta.tone,
    rawStatus,
    versionLabel,
    revisionId,
    staleReason,
    summary,
    isConfirmed: status === 'confirmed',
    isOutdated: status === 'outdated',
    canPublishToKnowledge: status === 'confirmed' && Boolean(summary || cardList.length > 0),
    openGapCount,
    updatedAt: handoff.updated_at || handoffResponse?.updated_at || '',
  };
}

function formatCardBullet(card) {
  const title = String(card?.title || '未命名对象').trim();
  const body = String(card?.summary || card?.content || '').trim();
  const status = card?.status ? ` [${card.status}]` : '';
  return body ? `- **${title}**${status}：${body}` : `- **${title}**${status}`;
}

/**
 * 派生面向下游 AI（Codex / Claude Code / Antigravity）的结构化 PRD Markdown。
 * 严禁将待澄清项或未拍板决策写成已完成结论。
 *
 * @param {Object} params
 * @param {string} params.title
 * @param {string} [params.workspaceId]
 * @param {Object} params.handoffView
 * @param {Array<Object>} [params.cards]
 * @param {string} [params.summary]
 * @returns {string}
 */
export function buildAiPrdMarkdown({
  title = 'EvoCanvas 项目',
  workspaceId = '',
  handoffView,
  cards = [],
  summary = '',
}) {
  const view = handoffView || normalizeHandoffView(null, cards);
  const cardList = Array.isArray(cards) ? cards : [];

  const evidences = cardList.filter((c) => String(c?.kind || '').toLowerCase() === 'evidence');
  const problems = cardList.filter((c) => String(c?.kind || '').toLowerCase() === 'problem');
  const constraints = cardList.filter((c) => String(c?.kind || '').toLowerCase() === 'constraint');
  const decisions = cardList.filter((c) => String(c?.kind || '').toLowerCase() === 'decision');
  const clarifications = cardList.filter((c) => String(c?.kind || '').toLowerCase() === 'clarification');

  const confirmedDecisions = decisions.filter((c) =>
    ['confirmed', 'decided', 'adopted', 'resolved'].includes(String(c?.status || '').toLowerCase()),
  );
  const pendingDecisions = decisions.filter((c) => !confirmedDecisions.includes(c));
  const openClarifications = clarifications.filter((c) =>
    !['resolved', 'answered', 'closed', 'archived', 'superseded'].includes(String(c?.status || '').toLowerCase()),
  );

  const lines = [
    `# ${title} — 面向 AI 的结构化需求交接（AI PRD）`,
    '',
    '> 本文档由 EvoCanvas 1.0 结构化交接物派生，供下游 AI 编程/评审工具直接消费。',
    '> **治理约束**：请严格遵守“已确认约束与决策”；对“仍未决边界”不得自行脑补或静默拍板。',
    '',
    '## 1. 版本与状态元信息',
    `- **工作区 ID**：\`${workspaceId || 'local'}\``,
    `- **交接状态**：${view.statusLabel}（\`${view.status}\`）`,
    `- **交接版本 / Revision**：\`${view.versionLabel}\`${view.revisionId ? `（\`${view.revisionId}\`）` : ''}`,
    `- **活跃未决缺口数**：${view.openGapCount}`,
  ];

  if (view.isOutdated && view.staleReason) {
    lines.push(`- **过时警告**：${view.staleReason}`);
  }

  const effectiveSummary = String(summary || view.summary || '').trim();
  if (effectiveSummary) {
    lines.push('', '## 2. 交接核心摘要', '', effectiveSummary);
  }

  lines.push('', '## 3. 核心问题定义');
  if (problems.length > 0) {
    lines.push(...problems.map(formatCardBullet));
  } else {
    lines.push('- 暂无已固定问题卡。');
  }

  lines.push('', '## 4. 已确认约束（必须遵守）');
  if (constraints.length > 0) {
    lines.push(...constraints.map(formatCardBullet));
  } else {
    lines.push('- 暂无已固定约束卡。');
  }

  lines.push('', '## 5. 已完成决策');
  if (confirmedDecisions.length > 0) {
    lines.push(...confirmedDecisions.map(formatCardBullet));
  } else {
    lines.push('- 暂无已完成决策。');
  }

  lines.push('', '## 6. 仍未决边界（严禁下游 AI 自行脑补）');
  if (openClarifications.length > 0 || pendingDecisions.length > 0) {
    if (openClarifications.length > 0) {
      lines.push('### 待澄清问题');
      lines.push(...openClarifications.map(formatCardBullet));
    }
    if (pendingDecisions.length > 0) {
      lines.push('### 待拍板决策');
      lines.push(...pendingDecisions.map(formatCardBullet));
    }
  } else {
    lines.push('- 当前无阻塞性未决项。');
  }

  lines.push('', '## 7. 关键背景与来源证据');
  if (evidences.length > 0) {
    lines.push(...evidences.map(formatCardBullet));
  } else {
    lines.push('- 请回看工作区原始输入与对话记录。');
  }

  return `${lines.join('\n')}\n`;
}
