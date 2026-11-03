/** 只保留卡片顺序和尚在提交的本地草稿；正式正文与状态始终来自最新投影。 */
export function reconcileCanvasProjection(current = {}, projected = {}) {
  return Object.fromEntries(Object.entries(projected).map(([section, cards]) => {
    const prior = current[section] || [];
    const order = new Map(prior.map((card, index) => [card.id, index]));
    const sorted = [...cards].sort((a, b) =>
      (order.get(a.id) ?? Number.MAX_SAFE_INTEGER) - (order.get(b.id) ?? Number.MAX_SAFE_INTEGER));
    const drafts = prior.filter(card => card.id?.startsWith('temp-') && !cards.some(item => item.id === card.id));
    return [section, [...sorted, ...drafts]];
  }));
}

const STATUS_LABELS = {
  collected: '已收录', cited: '已引用', archived: '已归档',
  initial: '待解决', converging: '收敛中', converged: '已收敛',
  open: '待澄清', pending_confirmation: '待确认', clarified: '已澄清', blocked: '已阻塞', closed: '已关闭',
  draft: '草稿', effective: '已生效', superseded: '已替代',
  pending_decision: '待决策', decided: '已决策',
  pending: '待确认', done: '已确认', confirmed: '已确认', approved: '已确认',
  suspended: '已过时', invalidated: '已过时',
};

export function getCanvasStatusLabel(status = '') {
  return STATUS_LABELS[status] || status;
}

export function isCanvasCardResolved(card) {
  if (['clarified', 'closed', 'effective', 'decided', 'converged', 'archived', 'superseded'].includes(card.status)) return true;
  return /(已确认|已审批|已完成|完成|关闭|closed|done|resolved)/i.test(`${card.status || ''} ${card.statusPill?.label || ''}`);
}

/** 正式对象按类型化状态判断缺口；历史演示卡可继续使用展示标签。 */
export function isActiveTypedGap(card) {
  const active = {
    clarification: ['open', 'pending_confirmation', 'blocked'],
    constraint: ['draft', 'pending_confirmation'],
    decision: ['pending_decision', 'pending_confirmation'],
  };
  const statuses = active[card.kind];
  if (!statuses) return undefined;
  if (statuses.includes(card.status)) return true;
  if (isCanvasCardResolved(card)) return false;
  return undefined;
}
