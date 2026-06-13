/**
 * @file quoteSelection.test.js
 * @description 针对文本引用与选择逻辑 (quoteSelection.js) 的单元测试。
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildQuoteDraft,
  summarizeQuoteDraft,
  appendQuoteDraft,
  clearQuoteDraft,
  buildDecisionPayload,
  buildQuoteTooltipLines,
  getQuoteTooltipLineClamp,
} from './quoteSelection.js';

// 测试追加多个不同来源的选择时，能正确聚合成单一的 draft 对象
test('appendQuoteDraft aggregates multiple selections into one draft', () => {
  const first = buildQuoteDraft({
    sourceType: 'message',
    sourceId: 'msg_1',
    sourceLabel: 'PM Agent',
    text: 'First line',
  });
  const second = buildQuoteDraft({
    sourceType: 'editor',
    sourceId: 'editor',
    sourceLabel: '文档编辑区',
    text: 'Second line',
  });

  const combined = appendQuoteDraft(null, first);
  const updated = appendQuoteDraft(combined, second);

  assert.equal(updated.items.length, 2);
  assert.equal(updated.items[0].text, 'First line');
  assert.equal(updated.items[1].sourceType, 'editor');
  assert.equal(summarizeQuoteDraft(updated), '2 个已选文本片段');
});

// 测试追加重复的引用源和文本时，去重机制应过滤掉重复项
test('appendQuoteDraft ignores duplicate source and text pairs', () => {
  const item = buildQuoteDraft({
    sourceType: 'message',
    sourceId: 'msg_1',
    sourceLabel: 'PM Agent',
    text: 'Repeated',
  });

  const combined = appendQuoteDraft(null, item);
  const duplicated = appendQuoteDraft(combined, item);

  assert.equal(duplicated.items.length, 1);
  assert.equal(summarizeQuoteDraft(duplicated), '1 个已选文本片段');
});

// 测试清空引用草稿状态，清空后应当返回 null
test('clearQuoteDraft resets the draft state', () => {
  const item = buildQuoteDraft({
    sourceType: 'message',
    sourceId: 'msg_1',
    sourceLabel: 'PM Agent',
    text: 'Repeated',
  });

  assert.equal(clearQuoteDraft(appendQuoteDraft(null, item)), null);
});

// 测试构造发给后端的决策 Payload 时，若包含引用项，需将其转换为下划线参数格式
test('buildDecisionPayload includes quoted selections only when present', () => {
  const item = buildQuoteDraft({
    sourceType: 'message',
    sourceId: 'msg_1',
    sourceLabel: 'PM Agent',
    text: 'A selected paragraph',
  });

  const payload = buildDecisionPayload('继续改这个点', appendQuoteDraft(null, item));

  assert.equal(payload.decision, '继续改这个点');
  assert.equal(payload.quoted_selections.length, 1);
  assert.deepEqual(payload.quoted_selections[0], {
    source_type: 'message',
    source_id: 'msg_1',
    source_label: 'PM Agent',
    text: 'A selected paragraph',
  });

  const plainPayload = buildDecisionPayload('纯文本消息', null);
  assert.equal('quoted_selections' in plainPayload, false);
});

// 测试格式化 Tooltip 展示行时，能交替渲染来源标签与引用内容
test('buildQuoteTooltipLines formats source-aware preview text', () => {
  const first = buildQuoteDraft({
    sourceType: 'message',
    sourceId: 'msg_1',
    sourceLabel: 'PM Agent',
    text: '第一段引用内容',
  });
  const second = buildQuoteDraft({
    sourceType: 'editor',
    sourceId: 'editor',
    sourceLabel: '文档编辑区',
    text: '第二段引用内容',
  });

  const lines = buildQuoteTooltipLines(appendQuoteDraft(appendQuoteDraft(null, first), second));

  assert.deepEqual(lines, [
    'PM Agent',
    '第一段引用内容',
    '文档编辑区',
    '第二段引用内容',
  ]);
});

// 测试当选中的单段引用文本太长时，能自动截断至 150 字符并追加省略号
test('buildQuoteTooltipLines truncates long quote text to 150 chars', () => {
  const item = buildQuoteDraft({
    sourceType: 'message',
    sourceId: 'msg_2',
    sourceLabel: 'QA Agent',
    text: 'a'.repeat(180),
  });

  const lines = buildQuoteTooltipLines(appendQuoteDraft(null, item));

  assert.equal(lines[0], 'QA Agent');
  assert.equal(lines[1].length, 151);
  assert.equal(lines[1].endsWith('…'), true);
});

// 测试当引用了多个条目时，为防 Tooltip 撑开，每个条目的字数预算应当动态缩减
test('buildQuoteTooltipLines shortens each segment when there are more quoted items', () => {
  const item1 = buildQuoteDraft({
    sourceType: 'message',
    sourceId: 'msg_1',
    sourceLabel: 'PM Agent',
    text: 'a'.repeat(180),
  });
  const item2 = buildQuoteDraft({
    sourceType: 'message',
    sourceId: 'msg_2',
    sourceLabel: 'QA Agent',
    text: 'b'.repeat(180),
  });
  const item3 = buildQuoteDraft({
    sourceType: 'editor',
    sourceId: 'editor',
    sourceLabel: '文档编辑区',
    text: 'c'.repeat(180),
  });

  const singleLines = buildQuoteTooltipLines(appendQuoteDraft(null, item1));
  const tripleDraft = appendQuoteDraft(appendQuoteDraft(appendQuoteDraft(null, item1), item2), item3);
  const tripleLines = buildQuoteTooltipLines(tripleDraft);

  assert.equal(singleLines[1].length, 151);
  assert.equal(tripleLines[1].length < singleLines[1].length, true);
  assert.equal(tripleLines[3].length, tripleLines[1].length);
  assert.equal(tripleLines[5].length, tripleLines[1].length);
});

// 测试随着引用条目的增多，行数显示限制 -webkit-line-clamp 也应对应减少
test('getQuoteTooltipLineClamp reduces lines as item count grows', () => {
  assert.equal(getQuoteTooltipLineClamp(1), 5);
  assert.equal(getQuoteTooltipLineClamp(2), 3);
  assert.equal(getQuoteTooltipLineClamp(3), 2);
  assert.equal(getQuoteTooltipLineClamp(6), 2);
});

