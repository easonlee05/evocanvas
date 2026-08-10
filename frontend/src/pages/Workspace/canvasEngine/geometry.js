/**
 * @file geometry.js
 * @description EvoCanvas 画布几何缓存与连接吸附。几何数据来自渲染层的布局结果，
 * 指针移动阶段只读取缓存，不重复遍历 DOM。
 */

import { CARD_PORTS, getPortPosition } from '../edgeRouter.js';

export const DEFAULT_CONNECT_SNAP_RADIUS = 64;
export const DEFAULT_EXPLICIT_PORT_SNAP_RADIUS = 20;

function toFiniteNumber(value, fallback = 0) {
  return Number.isFinite(value) ? value : fallback;
}

/**
 * 将 DOM 采样得到的原始几何（{left,right,top,bottom,width,height,id}）
 * 归一化为 element model：{id, x, y, width, height, version, boundElements}。
 * x/y 为画布坐标左上角，version 单调递增用于缓存失效判断。
 */
export function normalizeCardGeometry(rawGeom, version = 0) {
  if (!rawGeom) return null;
  const left = toFiniteNumber(rawGeom.left);
  const top = toFiniteNumber(rawGeom.top);
  const width = toFiniteNumber(rawGeom.width, rawGeom.right - left);
  const height = toFiniteNumber(rawGeom.height, rawGeom.bottom - top);
  return {
    id: rawGeom.id || null,
    x: left,
    y: top,
    width: Math.max(0, width),
    height: Math.max(0, height),
    // 兼容旧接口：edgeRouter / CustomArrow 读取的 rect 字段。
    left,
    right: left + Math.max(0, width),
    top,
    bottom: top + Math.max(0, height),
    version,
    boundElements: [],
  };
}

/**
 * 构建反向索引：cardId -> boundArrowIds[]。
 * 借鉴 Excalidraw 的 boundElements 反向索引，让箭头重算只遍历真正相连的卡片。
 */
export function buildBoundElementsIndex(arrows = []) {
  const index = {};
  (arrows || []).forEach((arrow) => {
    if (!arrow) return;
    const { start, end } = arrow;
    const arrowId = arrow.id ?? getArrowStableKey(start, end);
    if (start) {
      index[start] = index[start] || [];
      if (!index[start].includes(arrowId)) index[start].push(arrowId);
    }
    if (end) {
      index[end] = index[end] || [];
      if (!index[end].includes(arrowId)) index[end].push(arrowId);
    }
  });
  return index;
}

function getArrowStableKey(start, end) {
  return `${start}->${end}`;
}

/**
 * doesNeedUpdate 等价物：给定反向索引与变化的卡片集合，判断该箭头是否受影响。
 * 仅当箭头的 start 或 end 卡片在 changedCardIds 中时才需要重算。
 */
export function shouldRecomputeForCards(boundIndex, changedCardIds) {
  if (!changedCardIds || changedCardIds.size === 0) return new Set();
  const affected = new Set();
  changedCardIds.forEach((cardId) => {
    (boundIndex?.[cardId] || []).forEach((arrowId) => affected.add(arrowId));
  });
  return affected;
}

/**
 * 归一化比例端口：在卡片几何上按 [0,1] 比例取锚点并落到对应边的 1/2 base 位置。
 * 借鉴 Excalidraw FixedPointBinding.fixedPoint，坐标变化时按比例重算，避免端点漂移。
 */
export function getStablePortPoint(cardGeom, port = 'right', fixedX = 0.5, fixedY = 0.5) {
  if (!cardGeom) return { x: 0, y: 0 };
  const x = cardGeom.x + Math.max(0, Math.min(1, toFiniteNumber(fixedX, 0.5))) * cardGeom.width;
  const y = cardGeom.y + Math.max(0, Math.min(1, toFiniteNumber(fixedY, 0.5))) * cardGeom.height;
  const insetX = 16;
  const insetY = 16;

  if (port === 'top') return { x, y: cardGeom.y };
  if (port === 'bottom') return { x, y: cardGeom.y + cardGeom.height };
  if (port === 'left') return { x: cardGeom.x, y };
  if (port === 'right') return { x: cardGeom.x + cardGeom.width, y };

  // 兜底：按最近边取归一化锚点，并夹在卡片内以内缩量。
  const clampedX = Math.max(cardGeom.x + insetX, Math.min(cardGeom.x + cardGeom.width - insetX, x));
  const clampedY = Math.max(cardGeom.y + insetY, Math.min(cardGeom.y + cardGeom.height - insetY, y));
  return { x: clampedX, y: clampedY };
}

function normalizeScale(scale) {
  return toFiniteNumber(scale, 1) > 0 ? toFiniteNumber(scale, 1) : 1;
}

export function getCanvasRectFromElement(element, containerRect, scale = 1, id = null) {
  if (!element || !containerRect) return null;

  const rect = element.getBoundingClientRect();
  const safeScale = normalizeScale(scale);
  const left = (rect.left - containerRect.left) / safeScale;
  const right = (rect.right - containerRect.left) / safeScale;
  const top = (rect.top - containerRect.top) / safeScale;
  const bottom = (rect.bottom - containerRect.top) / safeScale;

  return {
    id: id || element.id || null,
    left: Math.min(left, right),
    right: Math.max(left, right),
    top: Math.min(top, bottom),
    bottom: Math.max(top, bottom),
    width: Math.abs(right - left),
    height: Math.abs(bottom - top),
  };
}

export function collectCardGeometry(elements, containerRect, scale = 1) {
  const geometry = {};

  (elements || []).forEach((element) => {
    const id = element?.id;
    if (!id) return;

    const rect = getCanvasRectFromElement(element, containerRect, scale, id);
    if (rect) geometry[id] = rect;
  });

  return geometry;
}

export function getCanvasPortPoint(rect, port = 'right') {
  return getPortPosition(rect, port);
}

export function resolveConnectionTargetAtPoint(
  point,
  geometry,
  startCardId,
  options = {},
) {
  const connectSnapRadius = options.connectSnapRadius ?? DEFAULT_CONNECT_SNAP_RADIUS;
  const explicitPortSnapRadius = options.explicitPortSnapRadius ?? DEFAULT_EXPLICIT_PORT_SNAP_RADIUS;

  let closestCardId = null;
  let closestPort = null;
  let closestDistance = Number.POSITIVE_INFINITY;
  let strongestExplicitMatch = null;

  Object.values(geometry || {}).forEach((rect) => {
    const cardId = rect?.id;
    if (!cardId || cardId === startCardId) return;

    const edgeCandidates = [
      {
        port: 'left',
        distance: Math.abs(point.x - rect.left),
        aligned: point.y >= rect.top - connectSnapRadius && point.y <= rect.bottom + connectSnapRadius,
      },
      {
        port: 'right',
        distance: Math.abs(point.x - rect.right),
        aligned: point.y >= rect.top - connectSnapRadius && point.y <= rect.bottom + connectSnapRadius,
      },
      {
        port: 'top',
        distance: Math.abs(point.y - rect.top),
        aligned: point.x >= rect.left - connectSnapRadius && point.x <= rect.right + connectSnapRadius,
      },
      {
        port: 'bottom',
        distance: Math.abs(point.y - rect.bottom),
        aligned: point.x >= rect.left - connectSnapRadius && point.x <= rect.right + connectSnapRadius,
      },
    ];

    edgeCandidates.forEach((candidate) => {
      if (!candidate.aligned || candidate.distance > explicitPortSnapRadius) return;
      if (!strongestExplicitMatch || candidate.distance < strongestExplicitMatch.distance) {
        strongestExplicitMatch = {
          cardId,
          port: candidate.port,
          distance: candidate.distance,
        };
      }
    });

    CARD_PORTS.forEach((port) => {
      const portPoint = getCanvasPortPoint(rect, port);
      const distance = Math.hypot(point.x - portPoint.x, point.y - portPoint.y);
      if (distance < closestDistance) {
        closestDistance = distance;
        closestCardId = cardId;
        closestPort = port;
      }
    });
  });

  if (strongestExplicitMatch) return strongestExplicitMatch;
  if (!closestCardId || !closestPort || closestDistance > connectSnapRadius) return null;

  return {
    cardId: closestCardId,
    port: closestPort,
    distance: closestDistance,
  };
}
