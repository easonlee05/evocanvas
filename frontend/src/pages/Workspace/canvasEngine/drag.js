/**
 * @file drag.js
 * @description 画布拖拽会话的纯逻辑。支持画布坐标和屏幕坐标两种拖拽空间。
 */

function toFiniteNumber(value, fallback = 0) {
  return Number.isFinite(value) ? value : fallback;
}

export function createDragSession({
  type,
  id,
  pointer,
  start,
  coordinateSpace = 'canvas',
  ...metadata
}) {
  return {
    ...metadata,
    type,
    id,
    pointerX: toFiniteNumber(pointer?.x),
    pointerY: toFiniteNumber(pointer?.y),
    startX: toFiniteNumber(start?.x),
    startY: toFiniteNumber(start?.y),
    coordinateSpace,
  };
}

export function getDragDelta(session, pointer, scale = 1) {
  const safeScale = toFiniteNumber(scale, 1) > 0 ? toFiniteNumber(scale, 1) : 1;
  const usesScreenSpace = session?.coordinateSpace === 'screen';

  return {
    x: usesScreenSpace
      ? toFiniteNumber(pointer?.x) - session.pointerX
      : (toFiniteNumber(pointer?.x) - session.pointerX) / safeScale,
    y: usesScreenSpace
      ? toFiniteNumber(pointer?.y) - session.pointerY
      : (toFiniteNumber(pointer?.y) - session.pointerY) / safeScale,
  };
}

export function getDraggedPosition(session, pointer, scale = 1) {
  const delta = getDragDelta(session, pointer, scale);
  return {
    x: session.startX + delta.x,
    y: session.startY + delta.y,
  };
}
