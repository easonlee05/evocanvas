import test from 'node:test';
import assert from 'node:assert/strict';
import { reconcileCanvasProjection, getCanvasStatusLabel, isActiveTypedGap } from './canvasProjection.js';

test('新 Revision 覆盖已有卡片正文和状态，保留展示顺序并移除已不在投影的对象', () => {
  const current = { clarify: [{ id: 'b', status: 'open', desc: '旧冲突' }, { id: 'a' }, { id: 'removed' }] };
  const projected = { clarify: [{ id: 'a' }, { id: 'b', status: 'clarified', desc: '用户已裁决' }] };
  const result = reconcileCanvasProjection(current, projected);
  assert.deepEqual(result.clarify, [{ id: 'b', status: 'clarified', desc: '用户已裁决' }, { id: 'a' }]);
  assert.equal(current.clarify[0].status, 'open');
});

test('刷新投影不会丢弃正在提交的本地新增草稿', () => {
  const draft = { id: 'temp-123', title: '正在提交' };
  assert.deepEqual(reconcileCanvasProjection({ rules: [draft] }, { rules: [] }).rules, [draft]);
});

test('已澄清、已生效和已决策不再因正文含冲突或口径而成为活跃缺口', () => {
  for (const [kind, status] of [['clarification', 'clarified'], ['constraint', 'effective'], ['decision', 'decided']]) {
    assert.equal(isActiveTypedGap({ kind, status, desc: '待确认口径，必须裁决' }), false);
  }
  assert.equal(isActiveTypedGap({ kind: 'decision', status: 'pending_decision' }), true);
  assert.equal(isActiveTypedGap({ kind: 'constraint', status: 'pending_confirmation' }), true);
  assert.equal(isActiveTypedGap({ kind: 'clarification', status: 'blocked' }), true);
  assert.equal(getCanvasStatusLabel('clarified'), '已澄清');
  assert.equal(getCanvasStatusLabel('effective'), '已生效');
  assert.equal(getCanvasStatusLabel('decided'), '已决策');
});
