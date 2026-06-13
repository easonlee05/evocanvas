/**
 * @file workspaceActions.test.js
 * @description 针对工作台动作辅助逻辑 (workspaceActions.js) 的单元测试。
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { shouldShowRunPrompt, getDocumentActionLabel } from './workspaceActions.js';

// 测试对于可恢复或尚未开始的任务，判定是否显示运行提示
test('shouldShowRunPrompt is true for resumable unfinished tasks', () => {
  assert.equal(shouldShowRunPrompt('created'), true);
  assert.equal(shouldShowRunPrompt('cancelled'), true);
  assert.equal(shouldShowRunPrompt('waiting_for_user'), true);
  assert.equal(shouldShowRunPrompt('completed'), false);
  assert.equal(shouldShowRunPrompt('failed'), false);
});

// 测试根据任务是否完成，返回正确的文档区按钮/操作提示文案
test('getDocumentActionLabel matches document availability', () => {
  assert.equal(getDocumentActionLabel({ done: true }), '查看文档');
  assert.equal(getDocumentActionLabel({ done: false }), '打开文档');
});

