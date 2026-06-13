/**
 * @file workspaceSession.test.js
 * @description 针对工作台会话自动化行为逻辑 (workspaceSession.js) 的单元测试。
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { shouldAutoOpenDocument, shouldAutoRunTaskOnOpen } from './workspaceSession.js';

// 测试在进入任务或遇到 Writer 事件时，是否依据用户历史行为正确决定自动打开文档面板
test('shouldAutoOpenDocument stays closed for existing tasks on entry and writer updates', () => {
  assert.equal(shouldAutoOpenDocument({ reason: 'task-entry', hasUserOpenedDoc: false }), false);
  assert.equal(shouldAutoOpenDocument({ reason: 'writer-event', hasUserOpenedDoc: false }), false);
  assert.equal(shouldAutoOpenDocument({ reason: 'writer-event', hasUserOpenedDoc: true }), true);
});

// 测试在打开页面时，是否不会自动开始运行未启动或已中断的任务（需要手动启动）
test('shouldAutoRunTaskOnOpen never auto-runs created or unfinished tasks on open', () => {
  assert.equal(shouldAutoRunTaskOnOpen({ rawStatus: 'created' }), false);
  assert.equal(shouldAutoRunTaskOnOpen({ rawStatus: 'running' }), false);
  assert.equal(shouldAutoRunTaskOnOpen({ rawStatus: 'waiting_for_user' }), false);
  assert.equal(shouldAutoRunTaskOnOpen({ rawStatus: 'cancelled' }), false);
});

