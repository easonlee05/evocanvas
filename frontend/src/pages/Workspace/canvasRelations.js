/**
 * @file canvasRelations.js
 * @description Canvas 关系图辅助逻辑，负责从卡片数据提取边关系并计算激活态可见性。
 */

export function flattenCanvasCards(sections) {
  return Object.values(sections).flat();
}

export function getArrowKey(arrow) {
  return `${arrow.start}->${arrow.end}`;
}

export function collectCanvasArrows(sections) {
  const cards = flattenCanvasCards(sections);
  const outConnections = {};
  const inConnections = {};
  const rawArrows = [];

  for (const card of cards) {
    if (!card.next) continue;

    const nextIds = Array.isArray(card.next) ? card.next : [card.next];
    for (const targetId of nextIds) {
      rawArrows.push({ start: card.id, end: targetId });

      if (!outConnections[card.id]) outConnections[card.id] = [];
      outConnections[card.id].push(targetId);

      if (!inConnections[targetId]) inConnections[targetId] = [];
      inConnections[targetId].push(card.id);
    }
  }

  return rawArrows.map((arrow) => {
    const startOuts = outConnections[arrow.start] || [];
    const endIns = inConnections[arrow.end] || [];

    return {
      ...arrow,
      startOffsetIndex: startOuts.indexOf(arrow.end),
      startOffsetTotal: startOuts.length,
      endOffsetIndex: endIns.indexOf(arrow.start),
      endOffsetTotal: endIns.length,
    };
  });
}

export function getRelatedCardIds(activeCardId, arrows) {
  if (!activeCardId) return new Set();

  const related = new Set([activeCardId]);
  for (const arrow of arrows) {
    if (arrow.start === activeCardId) related.add(arrow.end);
    if (arrow.end === activeCardId) related.add(arrow.start);
  }
  return related;
}

export function getArrowVisualState(arrow, activeCardId) {
  if (!activeCardId) return 'muted';
  if (arrow.start === activeCardId || arrow.end === activeCardId) return 'active';
  return 'hidden';
}

export function getArrowPresentation(arrow, activeCardId) {
  const visualState = getArrowVisualState(arrow, activeCardId);
  return {
    visualState,
    routeMode: 'default',
  };
}

const RELATION_COLORS = ['#3b82f6', '#f59e0b', '#10b981', '#8b5cf6', '#ef4444', '#06b6d4'];

export function getFocusedRelationColors(arrows, activeCardId) {
  if (!activeCardId) return {};

  const directEdges = arrows.filter((arrow) => arrow.start === activeCardId || arrow.end === activeCardId);
  const colors = {};

  directEdges.forEach((arrow, index) => {
    colors[getArrowKey(arrow)] = RELATION_COLORS[index % RELATION_COLORS.length];
  });

  return colors;
}
