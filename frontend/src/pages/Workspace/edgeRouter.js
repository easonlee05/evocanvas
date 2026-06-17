/**
 * @file edgeRouter.js
 * @description EvoCanvas 画布关系边路由器，负责将卡片端口连接为避开卡片的正交折线。
 */

export const CARD_PORTS = ['top', 'right', 'bottom', 'left'];

const DEFAULT_PADDING = 18;
const DEFAULT_CHANNEL_GAP = 30;
const DEFAULT_PORT_ESCAPE = 40;
const DEFAULT_CORNER_RADIUS = 12;
const PARALLEL_EDGE_GAP = 14;
const EPSILON = 0.001;

function toFiniteNumber(value, fallback = 0) {
  return Number.isFinite(value) ? value : fallback;
}

export function normalizeRect(rect, id = null) {
  if (!rect) return null;

  const left = Math.min(toFiniteNumber(rect.left), toFiniteNumber(rect.right));
  const right = Math.max(toFiniteNumber(rect.left), toFiniteNumber(rect.right));
  const top = Math.min(toFiniteNumber(rect.top), toFiniteNumber(rect.bottom));
  const bottom = Math.max(toFiniteNumber(rect.top), toFiniteNumber(rect.bottom));

  return {
    id: rect.id || id,
    left,
    right,
    top,
    bottom,
    width: right - left,
    height: bottom - top,
  };
}

function inflateRect(rect, padding) {
  return {
    ...rect,
    left: rect.left - padding,
    right: rect.right + padding,
    top: rect.top - padding,
    bottom: rect.bottom + padding,
  };
}

function rectCenter(rect) {
  return {
    x: (rect.left + rect.right) / 2,
    y: (rect.top + rect.bottom) / 2,
  };
}

export function getPortVector(port) {
  if (port === 'top') return { x: 0, y: -1 };
  if (port === 'bottom') return { x: 0, y: 1 };
  if (port === 'left') return { x: -1, y: 0 };
  return { x: 1, y: 0 };
}

function getParallelOffset(index = 0, total = 1) {
  if (!Number.isFinite(total) || total <= 1) return 0;
  return (toFiniteNumber(index) - (total - 1) / 2) * PARALLEL_EDGE_GAP;
}

function clamp(value, min, max) {
  if (min > max) return (min + max) / 2;
  return Math.max(min, Math.min(max, value));
}

export function getPortPosition(rect, port = 'right', offset = 0) {
  const safeRect = normalizeRect(rect);
  if (!safeRect) return { x: 0, y: 0 };

  const center = rectCenter(safeRect);
  const inset = 16;

  if (port === 'top') {
    return {
      x: clamp(center.x + offset, safeRect.left + inset, safeRect.right - inset),
      y: safeRect.top,
    };
  }

  if (port === 'bottom') {
    return {
      x: clamp(center.x + offset, safeRect.left + inset, safeRect.right - inset),
      y: safeRect.bottom,
    };
  }

  if (port === 'left') {
    return {
      x: safeRect.left,
      y: clamp(center.y + offset, safeRect.top + inset, safeRect.bottom - inset),
    };
  }

  return {
    x: safeRect.right,
    y: clamp(center.y + offset, safeRect.top + inset, safeRect.bottom - inset),
  };
}

function pushPoint(point, port, distance) {
  const vector = getPortVector(port);
  return {
    x: point.x + vector.x * distance,
    y: point.y + vector.y * distance,
  };
}

function pickDefaultPortPair(sourceRect, targetRect) {
  const sourceCenter = rectCenter(sourceRect);
  const targetCenter = rectCenter(targetRect);
  const dx = targetCenter.x - sourceCenter.x;
  const dy = targetCenter.y - sourceCenter.y;

  if (Math.abs(dx) >= Math.abs(dy)) {
    return dx >= 0
      ? { sourcePort: 'right', targetPort: 'left' }
      : { sourcePort: 'left', targetPort: 'right' };
  }

  return dy >= 0
    ? { sourcePort: 'bottom', targetPort: 'top' }
    : { sourcePort: 'top', targetPort: 'bottom' };
}

function scorePortPair(sourceRect, targetRect, sourcePort, targetPort) {
  const sourcePoint = getPortPosition(sourceRect, sourcePort);
  const targetPoint = getPortPosition(targetRect, targetPort);
  const sourceVector = getPortVector(sourcePort);
  const targetVector = getPortVector(targetPort);
  const dx = targetPoint.x - sourcePoint.x;
  const dy = targetPoint.y - sourcePoint.y;
  const distance = Math.abs(dx) + Math.abs(dy);
  const sourceAlignment = dx * sourceVector.x + dy * sourceVector.y;
  const targetAlignment = -dx * targetVector.x + -dy * targetVector.y;
  const badDirectionPenalty = (sourceAlignment < 0 ? 600 : 0) + (targetAlignment < 0 ? 600 : 0);
  const sameAxisBonus = (sourcePort === 'left' || sourcePort === 'right') === (targetPort === 'left' || targetPort === 'right') ? -40 : 0;

  return distance + badDirectionPenalty + sameAxisBonus;
}

function getBestPortPair(sourceRect, targetRect, preferredSourcePort, preferredTargetPort) {
  if (CARD_PORTS.includes(preferredSourcePort) && CARD_PORTS.includes(preferredTargetPort)) {
    return { sourcePort: preferredSourcePort, targetPort: preferredTargetPort };
  }

  if (CARD_PORTS.includes(preferredSourcePort)) {
    let bestTargetPort = 'left';
    let bestScore = Number.POSITIVE_INFINITY;
    CARD_PORTS.forEach((targetPort) => {
      const score = scorePortPair(sourceRect, targetRect, preferredSourcePort, targetPort);
      if (score < bestScore) {
        bestScore = score;
        bestTargetPort = targetPort;
      }
    });
    return { sourcePort: preferredSourcePort, targetPort: bestTargetPort };
  }

  if (CARD_PORTS.includes(preferredTargetPort)) {
    let bestSourcePort = 'right';
    let bestScore = Number.POSITIVE_INFINITY;
    CARD_PORTS.forEach((sourcePort) => {
      const score = scorePortPair(sourceRect, targetRect, sourcePort, preferredTargetPort);
      if (score < bestScore) {
        bestScore = score;
        bestSourcePort = sourcePort;
      }
    });
    return { sourcePort: bestSourcePort, targetPort: preferredTargetPort };
  }

  let bestPair = pickDefaultPortPair(sourceRect, targetRect);
  let bestScore = Number.POSITIVE_INFINITY;
  CARD_PORTS.forEach((sourcePort) => {
    CARD_PORTS.forEach((targetPort) => {
      const score = scorePortPair(sourceRect, targetRect, sourcePort, targetPort);
      if (score < bestScore) {
        bestScore = score;
        bestPair = { sourcePort, targetPort };
      }
    });
  });
  return bestPair;
}

function pointInsideRect(point, rect) {
  return (
    point.x > rect.left + EPSILON &&
    point.x < rect.right - EPSILON &&
    point.y > rect.top + EPSILON &&
    point.y < rect.bottom - EPSILON
  );
}

function pointBlocked(point, obstacles) {
  return obstacles.some((rect) => pointInsideRect(point, rect));
}

export function segmentIntersectsRect(a, b, rect) {
  if (Math.abs(a.y - b.y) < EPSILON) {
    const y = a.y;
    const minX = Math.min(a.x, b.x);
    const maxX = Math.max(a.x, b.x);
    return y >= rect.top - EPSILON && y <= rect.bottom + EPSILON && maxX > rect.left + EPSILON && minX < rect.right - EPSILON;
  }

  if (Math.abs(a.x - b.x) < EPSILON) {
    const x = a.x;
    const minY = Math.min(a.y, b.y);
    const maxY = Math.max(a.y, b.y);
    return x >= rect.left - EPSILON && x <= rect.right + EPSILON && maxY > rect.top + EPSILON && minY < rect.bottom - EPSILON;
  }

  return true;
}

function segmentBlocked(a, b, obstacles) {
  if (Math.abs(a.x - b.x) >= EPSILON && Math.abs(a.y - b.y) >= EPSILON) return true;
  return obstacles.some((rect) => segmentIntersectsRect(a, b, rect));
}

function keyForPoint(point) {
  return `${roundCoord(point.x)},${roundCoord(point.y)}`;
}

function roundCoord(value) {
  return Math.round(value * 1000) / 1000;
}

function uniqueSorted(values) {
  return [...new Set(values.map(roundCoord))].sort((a, b) => a - b);
}

function addChannelCoordinates(values, rect, axis, gap) {
  if (axis === 'x') {
    values.push(rect.left - gap, rect.right + gap, (rect.left + rect.right) / 2);
    return;
  }

  values.push(rect.top - gap, rect.bottom + gap, (rect.top + rect.bottom) / 2);
}

function buildGrid(start, end, obstacles, channelGap) {
  const xs = [start.x, end.x];
  const ys = [start.y, end.y];

  obstacles.forEach((rect) => {
    addChannelCoordinates(xs, rect, 'x', channelGap);
    addChannelCoordinates(ys, rect, 'y', channelGap);
  });

  xs.push((start.x + end.x) / 2);
  ys.push((start.y + end.y) / 2);

  const sortedXs = uniqueSorted(xs);
  const sortedYs = uniqueSorted(ys);
  const nodes = new Map();

  sortedXs.forEach((x) => {
    sortedYs.forEach((y) => {
      const point = { x, y };
      if (!pointBlocked(point, obstacles)) {
        nodes.set(keyForPoint(point), point);
      }
    });
  });

  nodes.set(keyForPoint(start), { x: roundCoord(start.x), y: roundCoord(start.y) });
  nodes.set(keyForPoint(end), { x: roundCoord(end.x), y: roundCoord(end.y) });

  return { nodes, xs: sortedXs, ys: sortedYs };
}

function getNeighbors(point, grid, obstacles) {
  const neighbors = [];
  const x = roundCoord(point.x);
  const y = roundCoord(point.y);
  const xIndex = grid.xs.indexOf(x);
  const yIndex = grid.ys.indexOf(y);

  for (let i = xIndex - 1; i >= 0; i -= 1) {
    const candidate = grid.nodes.get(`${grid.xs[i]},${y}`);
    if (!candidate) continue;
    if (!segmentBlocked(point, candidate, obstacles)) neighbors.push(candidate);
    break;
  }

  for (let i = xIndex + 1; i < grid.xs.length; i += 1) {
    const candidate = grid.nodes.get(`${grid.xs[i]},${y}`);
    if (!candidate) continue;
    if (!segmentBlocked(point, candidate, obstacles)) neighbors.push(candidate);
    break;
  }

  for (let i = yIndex - 1; i >= 0; i -= 1) {
    const candidate = grid.nodes.get(`${x},${grid.ys[i]}`);
    if (!candidate) continue;
    if (!segmentBlocked(point, candidate, obstacles)) neighbors.push(candidate);
    break;
  }

  for (let i = yIndex + 1; i < grid.ys.length; i += 1) {
    const candidate = grid.nodes.get(`${x},${grid.ys[i]}`);
    if (!candidate) continue;
    if (!segmentBlocked(point, candidate, obstacles)) neighbors.push(candidate);
    break;
  }

  return neighbors;
}

function directionBetween(a, b) {
  if (!a || !b) return null;
  if (Math.abs(a.x - b.x) < EPSILON) return 'v';
  if (Math.abs(a.y - b.y) < EPSILON) return 'h';
  return 'd';
}

function findGridRoute(start, end, obstacles, channelGap) {
  const grid = buildGrid(start, end, obstacles, channelGap);
  const startKey = keyForPoint(start);
  const endKey = keyForPoint(end);
  const distances = new Map([[startKey, 0]]);
  const previous = new Map();
  const previousDirection = new Map();
  const queue = [startKey];

  while (queue.length) {
    queue.sort((a, b) => distances.get(a) - distances.get(b));
    const currentKey = queue.shift();
    if (currentKey === endKey) break;

    const current = grid.nodes.get(currentKey);
    if (!current) continue;

    getNeighbors(current, grid, obstacles).forEach((next) => {
      const nextKey = keyForPoint(next);
      const direction = directionBetween(current, next);
      const length = Math.abs(next.x - current.x) + Math.abs(next.y - current.y);
      const bendPenalty = previousDirection.get(currentKey) && previousDirection.get(currentKey) !== direction ? 26 : 0;
      const nextDistance = distances.get(currentKey) + length + bendPenalty;

      if (nextDistance < (distances.get(nextKey) ?? Number.POSITIVE_INFINITY)) {
        distances.set(nextKey, nextDistance);
        previous.set(nextKey, currentKey);
        previousDirection.set(nextKey, direction);
        if (!queue.includes(nextKey)) queue.push(nextKey);
      }
    });
  }

  if (!previous.has(endKey) && startKey !== endKey) return null;

  const route = [];
  let cursor = endKey;
  route.push(grid.nodes.get(cursor));

  while (cursor !== startKey) {
    cursor = previous.get(cursor);
    if (!cursor) return null;
    route.push(grid.nodes.get(cursor));
  }

  return route.reverse();
}

function buildFallbackRoute(start, end, sourcePort, targetPort) {
  const sourceHorizontal = sourcePort === 'left' || sourcePort === 'right';
  const targetHorizontal = targetPort === 'left' || targetPort === 'right';

  if (sourceHorizontal || targetHorizontal) {
    const midX = (start.x + end.x) / 2;
    return [start, { x: midX, y: start.y }, { x: midX, y: end.y }, end];
  }

  const midY = (start.y + end.y) / 2;
  return [start, { x: start.x, y: midY }, { x: end.x, y: midY }, end];
}

export function simplifyOrthogonalPoints(points) {
  const deduped = [];

  points.forEach((point) => {
    const rounded = { x: roundCoord(point.x), y: roundCoord(point.y) };
    const last = deduped[deduped.length - 1];
    if (!last || Math.abs(last.x - rounded.x) > EPSILON || Math.abs(last.y - rounded.y) > EPSILON) {
      deduped.push(rounded);
    }
  });

  let changed = true;
  while (changed) {
    changed = false;
    for (let i = 1; i < deduped.length - 1; i += 1) {
      const prev = deduped[i - 1];
      const current = deduped[i];
      const next = deduped[i + 1];
      const sameX = Math.abs(prev.x - current.x) < EPSILON && Math.abs(current.x - next.x) < EPSILON;
      const sameY = Math.abs(prev.y - current.y) < EPSILON && Math.abs(current.y - next.y) < EPSILON;
      if (sameX || sameY) {
        deduped.splice(i, 1);
        changed = true;
        break;
      }
    }
  }

  return deduped;
}

export function buildSvgPath(points, radius = DEFAULT_CORNER_RADIUS) {
  const cleanPoints = simplifyOrthogonalPoints(points);
  if (!cleanPoints.length) return '';
  if (cleanPoints.length === 1) return `M ${cleanPoints[0].x} ${cleanPoints[0].y}`;
  if (cleanPoints.length === 2) return `M ${cleanPoints[0].x} ${cleanPoints[0].y} L ${cleanPoints[1].x} ${cleanPoints[1].y}`;

  const segments = [`M ${cleanPoints[0].x} ${cleanPoints[0].y}`];

  for (let i = 1; i < cleanPoints.length - 1; i += 1) {
    const prev = cleanPoints[i - 1];
    const current = cleanPoints[i];
    const next = cleanPoints[i + 1];
    const inDx = current.x - prev.x;
    const inDy = current.y - prev.y;
    const outDx = next.x - current.x;
    const outDy = next.y - current.y;
    const inLength = Math.hypot(inDx, inDy);
    const outLength = Math.hypot(outDx, outDy);

    if (inLength < EPSILON || outLength < EPSILON) continue;

    const actualRadius = Math.min(radius, inLength / 2, outLength / 2);
    const inUnit = { x: inDx / inLength, y: inDy / inLength };
    const outUnit = { x: outDx / outLength, y: outDy / outLength };
    const lineEnd = {
      x: roundCoord(current.x - inUnit.x * actualRadius),
      y: roundCoord(current.y - inUnit.y * actualRadius),
    };
    const curveEnd = {
      x: roundCoord(current.x + outUnit.x * actualRadius),
      y: roundCoord(current.y + outUnit.y * actualRadius),
    };

    segments.push(`L ${lineEnd.x} ${lineEnd.y}`);
    segments.push(`Q ${current.x} ${current.y}, ${curveEnd.x} ${curveEnd.y}`);
  }

  const last = cleanPoints[cleanPoints.length - 1];
  segments.push(`L ${last.x} ${last.y}`);
  return segments.join(' ');
}

function getPolylineMidPoint(points) {
  if (!points.length) return null;

  let totalLength = 0;
  for (let i = 1; i < points.length; i += 1) {
    totalLength += Math.abs(points[i].x - points[i - 1].x) + Math.abs(points[i].y - points[i - 1].y);
  }

  if (totalLength < EPSILON) return points[Math.floor(points.length / 2)] || points[0];

  let walked = 0;
  const target = totalLength / 2;

  for (let i = 1; i < points.length; i += 1) {
    const prev = points[i - 1];
    const current = points[i];
    const length = Math.abs(current.x - prev.x) + Math.abs(current.y - prev.y);
    if (walked + length >= target) {
      const ratio = (target - walked) / length;
      return {
        x: roundCoord(prev.x + (current.x - prev.x) * ratio),
        y: roundCoord(prev.y + (current.y - prev.y) * ratio),
      };
    }
    walked += length;
  }

  return points[points.length - 1];
}

function getLastSegment(points) {
  for (let i = points.length - 1; i > 0; i -= 1) {
    const end = points[i];
    const start = points[i - 1];
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const length = Math.hypot(dx, dy);
    if (length > EPSILON) {
      return { start, end, dx, dy, length };
    }
  }

  return null;
}

export function buildArrowHead(points, size = 10, width = 7) {
  const segment = getLastSegment(points);
  if (!segment) return '';

  const unitX = segment.dx / segment.length;
  const unitY = segment.dy / segment.length;
  const tip = segment.end;
  const base = {
    x: tip.x - unitX * size,
    y: tip.y - unitY * size,
  };
  const normal = {
    x: -unitY,
    y: unitX,
  };
  const left = {
    x: roundCoord(base.x + normal.x * width),
    y: roundCoord(base.y + normal.y * width),
  };
  const right = {
    x: roundCoord(base.x - normal.x * width),
    y: roundCoord(base.y - normal.y * width),
  };

  return `${roundCoord(tip.x)},${roundCoord(tip.y)} ${left.x},${left.y} ${right.x},${right.y}`;
}

function normalizeObstacles(obstacles, padding) {
  return (obstacles || [])
    .map((rect) => normalizeRect(rect))
    .filter(Boolean)
    .map((rect) => inflateRect(rect, padding));
}

function inferTargetPort(sourcePoint, targetPoint) {
  const dx = targetPoint.x - sourcePoint.x;
  const dy = targetPoint.y - sourcePoint.y;
  if (Math.abs(dx) >= Math.abs(dy)) return dx >= 0 ? 'left' : 'right';
  return dy >= 0 ? 'top' : 'bottom';
}

export function routeEdge(options) {
  const {
    sourceRect,
    targetRect,
    targetPoint,
    sourcePort: preferredSourcePort,
    targetPort: preferredTargetPort,
    sourceOffsetIndex = 0,
    sourceOffsetTotal = 1,
    targetOffsetIndex = 0,
    targetOffsetTotal = 1,
    obstacles = [],
    padding = DEFAULT_PADDING,
    channelGap = DEFAULT_CHANNEL_GAP,
    portEscape = DEFAULT_PORT_ESCAPE,
  } = options || {};

  const normalizedSource = normalizeRect(sourceRect);
  const normalizedTarget = normalizeRect(targetRect);
  if (!normalizedSource) return { path: '', points: [], midPoint: null };

  const hasTargetRect = Boolean(normalizedTarget);
  const sourceTargetPoint = hasTargetRect ? rectCenter(normalizedTarget) : targetPoint;
  if (!sourceTargetPoint) return { path: '', points: [], midPoint: null };

  const pair = hasTargetRect
    ? getBestPortPair(normalizedSource, normalizedTarget, preferredSourcePort, preferredTargetPort)
    : {
        sourcePort: CARD_PORTS.includes(preferredSourcePort) ? preferredSourcePort : pickDefaultPortPair(normalizedSource, {
          ...normalizedSource,
          left: sourceTargetPoint.x,
          right: sourceTargetPoint.x,
          top: sourceTargetPoint.y,
          bottom: sourceTargetPoint.y,
        }).sourcePort,
        targetPort: CARD_PORTS.includes(preferredTargetPort)
          ? preferredTargetPort
          : inferTargetPort(rectCenter(normalizedSource), sourceTargetPoint),
      };

  const sourcePoint = getPortPosition(
    normalizedSource,
    pair.sourcePort,
    getParallelOffset(sourceOffsetIndex, sourceOffsetTotal),
  );
  const endPoint = hasTargetRect
    ? getPortPosition(normalizedTarget, pair.targetPort, getParallelOffset(targetOffsetIndex, targetOffsetTotal))
    : { x: roundCoord(sourceTargetPoint.x), y: roundCoord(sourceTargetPoint.y) };

  const escapedStart = pushPoint(sourcePoint, pair.sourcePort, portEscape);
  const escapedEnd = hasTargetRect ? pushPoint(endPoint, pair.targetPort, portEscape) : endPoint;
  const inflatedObstacles = normalizeObstacles(obstacles, padding);
  const gridRoute = findGridRoute(escapedStart, escapedEnd, inflatedObstacles, channelGap)
    || buildFallbackRoute(escapedStart, escapedEnd, pair.sourcePort, pair.targetPort);
  const points = simplifyOrthogonalPoints([sourcePoint, ...gridRoute, endPoint]);

  return {
    path: buildSvgPath(points),
    arrowHead: buildArrowHead(points),
    points,
    midPoint: getPolylineMidPoint(points),
    sourcePort: pair.sourcePort,
    targetPort: pair.targetPort,
    sourcePoint,
    targetPoint: endPoint,
  };
}
