/**
 * @file sidebarHistory.test.js
 * @description 针对侧边栏历史数据扁平化工具函数 (sidebarHistory.js) 的单元测试。
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { flattenConversationGroups } from './sidebarHistory.js';

// 测试扁平化逻辑是否能按照时间线顺序（今天、昨天、更早）正确重组数据
test('flattenConversationGroups keeps chronological section order without extra footer row', () => {
  const items = flattenConversationGroups({
    today: [{ id: 't1', label: '今天任务', time: '10:00' }],
    yesterday: [{ id: 'y1', label: '昨天任务', time: '09:00' }],
    older: [{ id: 'o1', label: '更早任务', time: '08:00' }],
  });

  assert.deepEqual(items, [
    { type: 'group', label: '今天' },
    { type: 'item', id: 't1', label: '今天任务', time: '10:00' },
    { type: 'group', label: '昨天' },
    { type: 'item', id: 'y1', label: '昨天任务', time: '09:00' },
    { type: 'group', label: '更早' },
    { type: 'item', id: 'o1', label: '更早任务', time: '08:00' },
  ]);
});
