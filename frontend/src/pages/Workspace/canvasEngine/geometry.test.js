/**
 * @file geometry.test.js
 * @description 验证画布卡片几何缓存和连接端口吸附。
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import {
  resolveConnectionTargetAtPoint,
  normalizeCardGeometry,
  buildBoundElementsIndex,
  shouldRecomputeForCards,
  getStablePortPoint,
} from './geometry.js';

const geometry = {
  source: { id: 'source', left: 0, right: 120, top: 0, bottom: 100, width: 120, height: 100 },
  target: { id: 'target', left: 240, right: 360, top: 0, bottom: 100, width: 120, height: 100 },
};

test('resolveConnectionTargetAtPoint prefers an explicit aligned port', () => {
  const target = resolveConnectionTargetAtPoint(
    { x: 240, y: 52 },
    geometry,
    'source',
  );

  assert.deepEqual(target, { cardId: 'target', port: 'left', distance: 0 });
});

test('resolveConnectionTargetAtPoint ignores the connection source card', () => {
  const target = resolveConnectionTargetAtPoint(
    { x: 120, y: 50 },
    geometry,
    'source',
  );

  assert.equal(target, null);
});

test('resolveConnectionTargetAtPoint returns null outside the snap radius', () => {
  const target = resolveConnectionTargetAtPoint(
    { x: 180, y: 260 },
    geometry,
    'source',
  );

  assert.equal(target, null);
});

test('normalizeCardGeometry converts raw rect to element model', () => {
  const model = normalizeCardGeometry(
    { id: 'a', left: 10, right: 130, top: 20, bottom: 120, width: 120, height: 100 },
    3,
  );

  assert.deepEqual(model, {
    id: 'a',
    x: 10,
    y: 20,
    width: 120,
    height: 100,
    left: 10,
    right: 130,
    top: 20,
    bottom: 120,
    version: 3,
    boundElements: [],
  });
});

test('normalizeCardGeometry returns null for empty input', () => {
  assert.equal(normalizeCardGeometry(null), null);
});

test('buildBoundElementsIndex maps each card to its bound arrows', () => {
  const arrows = [
    { id: 'e1', start: 'a', end: 'b' },
    { id: 'e2', start: 'b', end: 'c' },
    { id: 'e3', start: 'a', end: 'c' },
  ];

  const index = buildBoundElementsIndex(arrows);

  assert.deepEqual(index.a, ['e1', 'e3']);
  assert.deepEqual(index.b, ['e1', 'e2']);
  assert.deepEqual(index.c, ['e2', 'e3']);
});

test('shouldRecomputeForCards only returns arrows bound to changed cards', () => {
  const index = buildBoundElementsIndex([
    { id: 'e1', start: 'a', end: 'b' },
    { id: 'e2', start: 'b', end: 'c' },
  ]);

  const affected = shouldRecomputeForCards(index, new Set(['a']));
  assert.deepEqual([...affected], ['e1']);

  const affectedBoth = shouldRecomputeForCards(index, new Set(['b']));
  assert.deepEqual([...affectedBoth].sort(), ['e1', 'e2']);

  const none = shouldRecomputeForCards(index, new Set(['x']));
  assert.equal(none.size, 0);
});

test('getStablePortPoint resolves proportional anchors on each edge', () => {
  const card = { id: 'a', x: 0, y: 0, width: 120, height: 100 };

  assert.deepEqual(getStablePortPoint(card, 'right'), { x: 120, y: 50 });
  assert.deepEqual(getStablePortPoint(card, 'left'), { x: 0, y: 50 });
  assert.deepEqual(getStablePortPoint(card, 'top'), { x: 60, y: 0 });
  assert.deepEqual(getStablePortPoint(card, 'bottom'), { x: 60, y: 100 });
});

test('getStablePortPoint follows the card when it moves', () => {
  const before = { id: 'a', x: 10, y: 20, width: 100, height: 80 };
  const after = { id: 'a', x: 50, y: 60, width: 100, height: 80 };

  const p0 = getStablePortPoint(before, 'right');
  const p1 = getStablePortPoint(after, 'right');

  // 移动后端点相对卡片保持同一归一化比例，且随卡片平移。
  assert.equal(p1.x - p0.x, 40);
  assert.equal(p1.y - p0.y, 40);
});
