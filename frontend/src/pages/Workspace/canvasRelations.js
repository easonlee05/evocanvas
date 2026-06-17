/**
 * @file canvasRelations.js
 * @description Canvas 关系图辅助逻辑，负责同步卡片连接、提取边关系并计算激活态可见性。
 */

const VALID_PORTS = new Set(['top', 'right', 'bottom', 'left']);

export function flattenCanvasCards(sections) {
  return Object.values(sections).flat();
}

export function getArrowKey(arrow) {
  return `${arrow.start}->${arrow.end}`;
}

function normalizePort(port) {
  return VALID_PORTS.has(port) ? port : null;
}

export function buildConnectionPortMap(relations = []) {
  const connectionPortMap = {};

  (relations || []).forEach((relation) => {
    const startId = relation.from_card_id || relation.source_id;
    const endId = relation.to_card_id || relation.target_id;
    if (!startId || !endId) return;

    const key = getArrowKey({ start: startId, end: endId });
    connectionPortMap[key] = {
      startPort: normalizePort(relation.metadata?.start_port),
      endPort: normalizePort(relation.metadata?.end_port),
    };
  });

  return connectionPortMap;
}

export function collectCanvasArrows(sections, connectionPortMap = {}) {
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
    const ports = connectionPortMap[getArrowKey(arrow)] || {};

    return {
      ...arrow,
      startOffsetIndex: startOuts.indexOf(arrow.end),
      startOffsetTotal: startOuts.length,
      endOffsetIndex: endIns.indexOf(arrow.start),
      endOffsetTotal: endIns.length,
      startPort: normalizePort(ports.startPort),
      endPort: normalizePort(ports.endPort),
    };
  });
}

export function findRelationId(relations = [], startId, endId) {
  const match = (relations || []).find((relation) => {
    const relationStartId = relation.from_card_id || relation.source_id;
    const relationEndId = relation.to_card_id || relation.target_id;
    return relationStartId === startId && relationEndId === endId;
  });

  return match?.relation_id || null;
}

function normalizeNextIds(next) {
  if (Array.isArray(next)) return next;
  if (next) return [next];
  return [];
}

export function applyConnectionToSections(sections, startId, endId) {
  const nextSections = {};

  Object.entries(sections).forEach(([sectionKey, cards]) => {
    nextSections[sectionKey] = cards.map((card) => {
      if (card.id !== startId) return card;

      const nextIds = normalizeNextIds(card.next);
      if (nextIds.includes(endId)) return card;

      return {
        ...card,
        next: [...nextIds, endId],
      };
    });
  });

  return nextSections;
}

export function removeConnectionFromSections(sections, startId, endId) {
  const nextSections = {};

  Object.entries(sections).forEach(([sectionKey, cards]) => {
    nextSections[sectionKey] = cards.map((card) => {
      if (card.id !== startId) return card;

      const nextIds = normalizeNextIds(card.next);
      const filteredNextIds = nextIds.filter((cardId) => cardId !== endId);
      if (filteredNextIds.length === nextIds.length) return card;

      return {
        ...card,
        next: filteredNextIds,
      };
    });
  });

  return nextSections;
}

export function syncSectionConnectionsFromRelations(sections, relations = []) {
  const nextMap = {};

  (relations || []).forEach((relation) => {
    const startId = relation.from_card_id || relation.source_id;
    const endId = relation.to_card_id || relation.target_id;
    if (!startId || !endId) return;

    if (!nextMap[startId]) nextMap[startId] = [];
    if (!nextMap[startId].includes(endId)) {
      nextMap[startId].push(endId);
    }
  });

  const nextSections = {};
  Object.entries(sections).forEach(([sectionKey, cards]) => {
    nextSections[sectionKey] = cards.map((card) => ({
      ...card,
      next: nextMap[card.id] || [],
    }));
  });

  return nextSections;
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
