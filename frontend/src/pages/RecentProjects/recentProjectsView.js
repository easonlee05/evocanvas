/**
 * @file recentProjectsView.js
 * @description 最近项目页的纯函数格式化工具，负责把 API 数据转成稳定的卡片展示字段。
 */

const STATUS_LABELS = {
  confirmed: '已确认交接',
  draft: '交接草稿',
  not_ready: '待收敛',
};

export function formatRelativeUpdateLabel(isoValue, now = new Date()) {
  if (!isoValue) return '尚未编辑';
  const updatedAt = new Date(isoValue);
  if (Number.isNaN(updatedAt.getTime())) return '尚未编辑';

  const diffMinutes = Math.max(0, Math.floor((now.getTime() - updatedAt.getTime()) / 60000));
  if (diffMinutes < 60) {
    return `编辑于 ${diffMinutes || 1} 分钟前`;
  }

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `编辑于 ${diffHours} 小时前`;
  }

  const diffDays = Math.floor(diffHours / 24);
  return `编辑于 ${diffDays} 天前`;
}

export function buildRecentProjectCard(item, now = new Date()) {
  return {
    workspaceId: item.workspace_id,
    title: item.title || '未命名项目',
    summary: item.summary_preview || '继续补充这张产品工作画布。',
    updatedLabel: formatRelativeUpdateLabel(item.updated_at, now),
    statusLabel: STATUS_LABELS[item.handoff_status] || '继续推进',
    coverMode: item.cover_mode || 'placeholder',
  };
}
