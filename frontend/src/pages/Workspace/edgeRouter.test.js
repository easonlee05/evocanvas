/**
 * @file edgeRouter.test.js
 * @description 验证 EvoCanvas 关系边路由器的正交、避障、端口和并行边策略。
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildArrowHead,
  getPortPosition,
  routeEdge,
  segmentIntersectsRect,
  simplifyOrthogonalPoints,
} from './edgeRouter.js';

const sourceRect = { id: 'source', left: 0, top: 40, right: 160, bottom: 140 };
const targetRect = { id: 'target', left: 420, top: 40, right: 580, bottom: 140 };

test('routeEdge creates only horizontal and vertical segments', () => {
  const route = routeEdge({
    sourceRect,
    targetRect,
    sourcePort: 'right',
    targetPort: 'left',
    obstacles: [sourceRect, targetRect],
  });

  assert.ok(route.points.length >= 2);
  assertAllSegmentsOrthogonal(route.points);
});

test('routeEdge leaves the exact requested source and target ports', () => {
  const route = routeEdge({
    sourceRect,
    targetRect,
    sourcePort: 'bottom',
    targetPort: 'top',
    obstacles: [sourceRect, targetRect],
  });

  assert.deepEqual(route.points[0], getPortPosition(sourceRect, 'bottom'));
  assert.deepEqual(route.points.at(-1), getPortPosition(targetRect, 'top'));
  assert.equal(route.points[1].y > route.points[0].y, true);
  assert.equal(route.points.at(-2).y < route.points.at(-1).y, true);
});

test('routeEdge avoids unrelated card rectangles instead of crossing through them', () => {
  const obstacle = { id: 'middle', left: 230, top: 0, right: 330, bottom: 180 };
  const route = routeEdge({
    sourceRect,
    targetRect,
    sourcePort: 'right',
    targetPort: 'left',
    obstacles: [sourceRect, targetRect, obstacle],
  });

  const middleSegments = route.points.slice(1, -1);
  for (let i = 1; i < middleSegments.length; i += 1) {
    assert.equal(
      segmentIntersectsRect(middleSegments[i - 1], middleSegments[i], inflate(obstacle, 18)),
      false,
      `segment ${i} should not cross the middle card`,
    );
  }
});

test('parallel edges use distinct side anchors to avoid total overlap', () => {
  const first = routeEdge({
    sourceRect,
    targetRect,
    sourcePort: 'right',
    targetPort: 'left',
    sourceOffsetIndex: 0,
    sourceOffsetTotal: 2,
    targetOffsetIndex: 0,
    targetOffsetTotal: 2,
    obstacles: [sourceRect, targetRect],
  });
  const second = routeEdge({
    sourceRect,
    targetRect,
    sourcePort: 'right',
    targetPort: 'left',
    sourceOffsetIndex: 1,
    sourceOffsetTotal: 2,
    targetOffsetIndex: 1,
    targetOffsetTotal: 2,
    obstacles: [sourceRect, targetRect],
  });

  assert.notDeepEqual(first.points[0], second.points[0]);
  assert.notDeepEqual(first.points.at(-1), second.points.at(-1));
});

test('buildArrowHead points toward the final segment endpoint', () => {
  const rightward = buildArrowHead([{ x: 0, y: 0 }, { x: 100, y: 0 }]);
  const leftward = buildArrowHead([{ x: 100, y: 0 }, { x: 0, y: 0 }]);
  const downward = buildArrowHead([{ x: 0, y: 0 }, { x: 0, y: 100 }]);
  const upward = buildArrowHead([{ x: 0, y: 100 }, { x: 0, y: 0 }]);

  assert.deepEqual(parseArrowPoints(rightward)[0], { x: 100, y: 0 });
  assert.equal(parseArrowPoints(rightward)[1].x < 100, true);
  assert.deepEqual(parseArrowPoints(leftward)[0], { x: 0, y: 0 });
  assert.equal(parseArrowPoints(leftward)[1].x > 0, true);
  assert.deepEqual(parseArrowPoints(downward)[0], { x: 0, y: 100 });
  assert.equal(parseArrowPoints(downward)[1].y < 100, true);
  assert.deepEqual(parseArrowPoints(upward)[0], { x: 0, y: 0 });
  assert.equal(parseArrowPoints(upward)[1].y > 0, true);
});

test('simplifyOrthogonalPoints removes duplicate and collinear points', () => {
  assert.deepEqual(
    simplifyOrthogonalPoints([
      { x: 0, y: 0 },
      { x: 0, y: 0 },
      { x: 40, y: 0 },
      { x: 80, y: 0 },
      { x: 80, y: 60 },
    ]),
    [
      { x: 0, y: 0 },
      { x: 80, y: 0 },
      { x: 80, y: 60 },
    ],
  );
});

function assertAllSegmentsOrthogonal(points) {
  for (let i = 1; i < points.length; i += 1) {
    const prev = points[i - 1];
    const current = points[i];
    assert.ok(
      prev.x === current.x || prev.y === current.y,
      `segment ${i} is diagonal: ${JSON.stringify(prev)} -> ${JSON.stringify(current)}`,
    );
  }
}

function parseArrowPoints(points) {
  return points.split(' ').map((point) => {
    const [x, y] = point.split(',').map(Number);
    return { x, y };
  });
}

function inflate(rect, padding) {
  return {
    left: rect.left - padding,
    right: rect.right + padding,
    top: rect.top - padding,
    bottom: rect.bottom + padding,
  };
}
