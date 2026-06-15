/**
 * @file recentProjectsView.test.js
 * @description 针对最近项目卡片视图格式化逻辑的纯函数测试。
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { buildRecentProjectCard, formatRelativeUpdateLabel } from './recentProjectsView.js';

test('buildRecentProjectCard fills safe defaults for untitled projects', () => {
  const card = buildRecentProjectCard({
    workspace_id: 'ws_123',
    title: '',
    updated_at: '',
    handoff_status: 'not_ready',
    summary_preview: '',
  });

  assert.equal(card.title, '未命名项目');
  assert.equal(card.summary, '继续补充这张产品工作画布。');
  assert.equal(card.statusLabel, '待收敛');
});

test('formatRelativeUpdateLabel returns recently edited copy for fresh timestamps', () => {
  assert.equal(
    formatRelativeUpdateLabel('2026-06-14T09:00:00Z', new Date('2026-06-14T09:20:00Z')),
    '编辑于 20 分钟前',
  );
});
