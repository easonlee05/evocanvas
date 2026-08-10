/**
 * @file viewport.test.js
 * @description 验证画布视口的坐标换算、平移和指针中心缩放。
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import {
  canvasPointToScreen,
  screenPointToCanvas,
  translateViewport,
  zoomViewportAtPoint,
} from './viewport.js';

test('screen and canvas coordinates are inverse operations', () => {
  const viewport = { x: 120, y: -40, scale: 1.5 };
  const canvasPoint = { x: 80, y: 30 };
  const screenPoint = canvasPointToScreen(canvasPoint, viewport);

  assert.deepEqual(screenPointToCanvas(screenPoint, viewport), canvasPoint);
});

test('translateViewport only changes viewport translation', () => {
  assert.deepEqual(
    translateViewport({ x: 10, y: 20, scale: 1.5 }, { x: -4, y: 8 }),
    { x: 6, y: 28, scale: 1.5 },
  );
});

test('zoomViewportAtPoint keeps the canvas point under the pointer fixed', () => {
  const viewport = { x: 0, y: 0, scale: 1 };
  const pointer = { x: 200, y: 100 };
  const nextViewport = zoomViewportAtPoint(viewport, pointer, -1);

  assert.deepEqual(screenPointToCanvas(pointer, viewport), screenPointToCanvas(pointer, nextViewport));
  assert.equal(nextViewport.scale, 1.1);
});
