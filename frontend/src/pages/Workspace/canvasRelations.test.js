/**
 * @file canvasRelations.test.js
 * @description 针对 Canvas 连线关系的辅助逻辑测试，确保默认弱显示与选中高亮策略稳定。
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { DEMO_CANVAS_SECTIONS } from './demoScenario.js';
import {
  collectCanvasArrows,
  getArrowKey,
  getArrowPresentation,
  getArrowVisualState,
  getFocusedRelationColors,
  getRelatedCardIds,
} from './canvasRelations.js';

test('collectCanvasArrows extracts graph edges with per-end offsets', () => {
  const arrows = collectCanvasArrows(DEMO_CANVAS_SECTIONS);
  const evidenceToProblem = arrows.find((arrow) => arrow.start === 'e1' && arrow.end === 'p1');

  assert.ok(arrows.length > 0, 'demo canvas should expose graph edges');
  assert.ok(evidenceToProblem, 'expected evidence to problem edge should exist');
  assert.equal(typeof evidenceToProblem.startOffsetIndex, 'number');
  assert.equal(typeof evidenceToProblem.endOffsetIndex, 'number');
});

test('getRelatedCardIds returns one-hop neighbors for the active card', () => {
  const arrows = collectCanvasArrows(DEMO_CANVAS_SECTIONS);
  const related = getRelatedCardIds('p1', arrows);

  assert.equal(related.has('p1'), true);
  assert.equal(related.has('e1'), true);
  assert.equal(related.has('e2'), true);
  assert.equal(related.has('c1'), true);
  assert.equal(related.has('r1'), true);
  assert.equal(related.has('d3'), false);
});

test('getArrowVisualState keeps defaults muted and only highlights active edges on selection', () => {
  const arrow = { start: 'e1', end: 'p1' };
  const unrelated = { start: 'c3', end: 'r3' };

  assert.equal(getArrowVisualState(arrow, null), 'muted');
  assert.equal(getArrowVisualState(arrow, 'p1'), 'active');
  assert.equal(getArrowVisualState(unrelated, 'p1'), 'hidden');
});

test('getArrowPresentation reroutes selected one-hop edges through whitespace channels', () => {
  const outgoing = { start: 'p1', end: 'c1' };
  const incoming = { start: 'e1', end: 'p1' };
  const unrelated = { start: 'r3', end: 'd3' };

  assert.deepEqual(getArrowPresentation(outgoing, 'p1'), {
    visualState: 'active',
    routeMode: 'default',
  });
  assert.deepEqual(getArrowPresentation(incoming, 'p1'), {
    visualState: 'active',
    routeMode: 'default',
  });
  assert.deepEqual(getArrowPresentation(unrelated, 'p1'), {
    visualState: 'hidden',
    routeMode: 'default',
  });
});

test('getFocusedRelationColors assigns distinct colors to direct active edges only', () => {
  const arrows = collectCanvasArrows(DEMO_CANVAS_SECTIONS);
  const colors = getFocusedRelationColors(arrows, 'p1');

  assert.ok(colors[getArrowKey({ start: 'e1', end: 'p1' })]);
  assert.ok(colors[getArrowKey({ start: 'e2', end: 'p1' })]);
  assert.ok(colors[getArrowKey({ start: 'p1', end: 'c1' })]);
  assert.equal(colors[getArrowKey({ start: 'r3', end: 'd3' })], undefined);
  assert.notEqual(
    colors[getArrowKey({ start: 'e1', end: 'p1' })],
    colors[getArrowKey({ start: 'e2', end: 'p1' })],
  );
});
