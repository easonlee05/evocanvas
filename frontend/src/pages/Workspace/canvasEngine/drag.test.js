/**
 * @file drag.test.js
 * @description 验证画布拖拽在画布坐标和屏幕坐标中的增量计算。
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { createDragSession, getDraggedPosition } from './drag.js';

test('canvas-space dragging divides pointer movement by zoom scale', () => {
  const session = createDragSession({
    type: 'card',
    id: 'card-1',
    pointer: { x: 100, y: 200 },
    start: { x: 20, y: 30 },
    coordinateSpace: 'canvas',
  });

  assert.deepEqual(getDraggedPosition(session, { x: 160, y: 260 }, 2), { x: 50, y: 60 });
});

test('screen-space dragging keeps the pointer delta in screen pixels', () => {
  const session = createDragSession({
    type: 'widget',
    id: 'widget-1',
    pointer: { x: 100, y: 200 },
    start: { x: 20, y: 30 },
    coordinateSpace: 'screen',
  });

  assert.deepEqual(getDraggedPosition(session, { x: 160, y: 260 }, 2), { x: 80, y: 90 });
});
