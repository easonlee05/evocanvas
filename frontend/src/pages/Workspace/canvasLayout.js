/**
 * @file canvasLayout.js
 * @description Canvas 布局计算辅助逻辑，负责卡片高度估算、碰撞整理与画布边界计算。
 */

export function estimateCardHeight(card) {
  let height = 32;

  if (card.title) height += 26;
  if (card.tags?.length || card.statusPill) height += 30;
  if (card.desc) {
    const descLength = card.desc.length;
    const descLines = Math.ceil(descLength / 34);
    height += Math.max(26, descLines * 20);
  } else {
    height += 22;
  }
  if (card.structuredItems?.length) {
    height += card.structuredItems.length * 22 + 12;
  }
  if (card.attachments?.length) {
    height += card.attachments.length * 20 + 8;
  }
  if (card.source || card.owner) height += 38;
  if (typeof card.confidence === 'number') height += 34;
  if (card.next?.length) height += 12;

  return Math.max(height, 156);
}

export function resolveCollisions(positions, allCards) {
  const MIN_Y_GAP = 28;
  const COLUMN_SNAP = 24;
  const columns = [];

  allCards.forEach((card) => {
    const pos = positions[card.id];
    if (!pos) return;

    const targetColumn = columns.find((column) => Math.abs(column[0].x - pos.x) < COLUMN_SNAP);
    if (targetColumn) {
      targetColumn.push({ id: card.id, x: pos.x, y: pos.y, height: estimateCardHeight(card) });
    } else {
      columns.push([{ id: card.id, x: pos.x, y: pos.y, height: estimateCardHeight(card) }]);
    }
  });

  columns.forEach((column) => {
    column.sort((a, b) => a.y - b.y);
    for (let index = 1; index < column.length; index += 1) {
      const previous = column[index - 1];
      const current = column[index];
      const minY = previous.y + previous.height + MIN_Y_GAP;
      if (current.y < minY) {
        positions[current.id] = {
          ...positions[current.id],
          y: minY,
        };
        current.y = minY;
      }
    }
  });

  return positions;
}

export function buildCompactSectionLayout(canvasSections) {
  const SECTION_LAYOUT = {
    evidence: { x: 72, y: 112 },
    problems: { x: 448, y: 112 },
    clarify: { x: 448, y: 480 },
    rules: { x: 856, y: 112 },
    options: { x: 856, y: 480 },
    planning: { x: 1248, y: 112 },
  };
  const CARD_GAP = 24;
  const COLUMN_WRAP_THRESHOLD = 4;
  const COLUMN_OFFSET_X = 352;
  const positions = {};

  Object.entries(canvasSections).forEach(([sectionKey, sectionCards]) => {
    const anchor = SECTION_LAYOUT[sectionKey] || { x: 72, y: 88 };
    let columnIndex = 0;
    let cursorY = anchor.y;

    sectionCards.forEach((card, index) => {
      if (index > 0 && index % COLUMN_WRAP_THRESHOLD === 0) {
        columnIndex += 1;
        cursorY = anchor.y;
      }

      positions[card.id] = {
        x: anchor.x + columnIndex * COLUMN_OFFSET_X,
        y: cursorY,
      };

      cursorY += estimateCardHeight(card) + CARD_GAP;
    });
  });

  return positions;
}

export function getCanvasBounds(cardPositions, cards) {
  let maxX = 1440;
  let maxY = 960;

  cards.forEach((card) => {
    const pos = cardPositions[card.id];
    if (!pos) return;

    maxX = Math.max(maxX, pos.x + 320 + 160);
    maxY = Math.max(maxY, pos.y + estimateCardHeight(card) + 200);
  });

  return { width: maxX, height: maxY };
}
