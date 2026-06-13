/**
 * @file workspaceContent.test.js
 * @description 针对工作台消息内容清洗逻辑的单元测试，避免流式光标字符泄露到界面。
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { sanitizeWorkspaceContent } from './workspaceContent.js';

test('sanitizeWorkspaceContent strips think tags, cursor glyphs, and trims whitespace', () => {
  assert.equal(
    sanitizeWorkspaceContent('  <think>internal</think>正在生成任务包……▋  '),
    '正在生成任务包……',
  );
});

test('sanitizeWorkspaceContent keeps ordinary markdown content intact', () => {
  assert.equal(
    sanitizeWorkspaceContent('**标题**\n\n- 列表项'),
    '**标题**\n\n- 列表项',
  );
});
