/**
 * @file viewport.js
 * @description EvoCanvas 画布视口数学。只处理屏幕坐标、画布坐标、平移和缩放，
 * 不包含卡片业务语义或 DOM 访问。
 */

export const DEFAULT_VIEWPORT = Object.freeze({ x: 0, y: 0, scale: 1 });
export const VIEWPORT_LIMITS = Object.freeze({ minScale: 0.2, maxScale: 3, scaleFactor: 1.1 });

function toFiniteNumber(value, fallback = 0) {
  return Number.isFinite(value) ? value : fallback;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

export function normalizeViewport(viewport = {}) {
  return {
    x: toFiniteNumber(viewport.x, DEFAULT_VIEWPORT.x),
    y: toFiniteNumber(viewport.y, DEFAULT_VIEWPORT.y),
    scale: clamp(
      toFiniteNumber(viewport.scale, DEFAULT_VIEWPORT.scale),
      VIEWPORT_LIMITS.minScale,
      VIEWPORT_LIMITS.maxScale,
    ),
  };
}

export function screenPointToCanvas(point, viewport = DEFAULT_VIEWPORT) {
  const safeViewport = normalizeViewport(viewport);
  return {
    x: (toFiniteNumber(point?.x) - safeViewport.x) / safeViewport.scale,
    y: (toFiniteNumber(point?.y) - safeViewport.y) / safeViewport.scale,
  };
}

export function canvasPointToScreen(point, viewport = DEFAULT_VIEWPORT) {
  const safeViewport = normalizeViewport(viewport);
  return {
    x: toFiniteNumber(point?.x) * safeViewport.scale + safeViewport.x,
    y: toFiniteNumber(point?.y) * safeViewport.scale + safeViewport.y,
  };
}

export function translateViewport(viewport, delta = {}) {
  const safeViewport = normalizeViewport(viewport);
  return {
    ...safeViewport,
    x: safeViewport.x + toFiniteNumber(delta.x),
    y: safeViewport.y + toFiniteNumber(delta.y),
  };
}

/**
 * Zoom around a screen-space point so that the canvas point under the pointer
 * remains fixed. This mirrors the expected infinite-canvas interaction without
 * coupling it to a particular renderer.
 */
export function zoomViewportAtPoint(
  viewport,
  screenPoint,
  deltaY,
  limits = VIEWPORT_LIMITS,
) {
  const safeViewport = normalizeViewport(viewport);
  const canvasPoint = screenPointToCanvas(screenPoint, safeViewport);
  const direction = deltaY < 0 ? 1 : -1;
  const nextScale = clamp(
    safeViewport.scale * (direction > 0 ? limits.scaleFactor : 1 / limits.scaleFactor),
    limits.minScale,
    limits.maxScale,
  );

  return {
    x: toFiniteNumber(screenPoint?.x) - canvasPoint.x * nextScale,
    y: toFiniteNumber(screenPoint?.y) - canvasPoint.y * nextScale,
    scale: nextScale,
  };
}

export function clientPointToCanvas(clientPoint, containerRect, viewport = DEFAULT_VIEWPORT) {
  if (!containerRect) return screenPointToCanvas(clientPoint, viewport);

  return screenPointToCanvas(
    {
      x: toFiniteNumber(clientPoint?.x) - toFiniteNumber(containerRect.left),
      y: toFiniteNumber(clientPoint?.y) - toFiniteNumber(containerRect.top),
    },
    viewport,
  );
}
