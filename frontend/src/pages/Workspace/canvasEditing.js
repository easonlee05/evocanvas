/**
 * @file canvasEditing.js
 * @description EvoCanvas 画布卡片编辑与迁移辅助逻辑，约束原地编辑、模块内排序与合法跨阶段迁移。
 */

export const SECTION_ORDER = ['evidence', 'problems', 'clarify', 'rules', 'planning'];

export const SECTION_META = {
  evidence: { label: '用户反馈', moveTitle: '证据' },
  problems: { label: '功能设计', moveTitle: '问题定义' },
  clarify: { label: '待澄清问题', moveTitle: '待澄清' },
  rules: { label: '决策确认', moveTitle: '已确认约束 / 待决策' },
  planning: { label: '迭代计划', moveTitle: '推进执行' },
};

const ALLOWED_SECTION_MOVES = {
  evidence: ['problems'],
  problems: ['clarify'],
  clarify: ['rules'],
  rules: ['planning'],
  planning: [],
};

export function createInitialCanvasSections(sections) {
  return Object.fromEntries(
    Object.entries(sections).map(([sectionKey, cards]) => [
      sectionKey,
      cards.map((card) => ({ ...card })),
    ]),
  );
}

export function getCardLocation(sections, cardId) {
  for (const [sectionKey, cards] of Object.entries(sections)) {
    const index = cards.findIndex((card) => card.id === cardId);
    if (index !== -1) {
      return { sectionKey, index, card: cards[index] };
    }
  }

  return null;
}

export function updateCanvasCard(sections, cardId, updates) {
  const location = getCardLocation(sections, cardId);
  if (!location) return sections;

  const nextSections = { ...sections };
  nextSections[location.sectionKey] = sections[location.sectionKey].map((card) =>
    card.id === cardId
      ? {
          ...card,
          ...(typeof updates.title === 'string' ? { title: updates.title } : {}),
          ...(typeof updates.desc === 'string' ? { desc: updates.desc } : {}),
          ...(Array.isArray(updates.structuredItems) ? { structuredItems: updates.structuredItems } : {}),
        }
      : card,
  );

  return nextSections;
}

export function reorderCanvasCards(sections, { fromSection, toSection, fromIndex, toIndex }) {
  if (fromSection !== toSection) {
    throw new Error('reorder only supports same-section moves');
  }

  const cards = [...sections[fromSection]];
  const [movedCard] = cards.splice(fromIndex, 1);

  if (!movedCard) return sections;

  const nextIndex = clampIndex(toIndex, cards.length);
  cards.splice(nextIndex, 0, movedCard);

  return {
    ...sections,
    [fromSection]: cards,
  };
}

export function isMoveAllowed({ fromSection, toSection }) {
  if (fromSection === toSection) return true;
  return ALLOWED_SECTION_MOVES[fromSection]?.includes(toSection) ?? false;
}

export function describeCanvasMove({ fromSection, toSection }) {
  if (fromSection === toSection) {
    return `在“${SECTION_META[fromSection]?.label || fromSection}”内调整卡片顺序`;
  }

  return `这张卡将从“${SECTION_META[fromSection]?.moveTitle || fromSection}”转为“${SECTION_META[toSection]?.moveTitle || toSection}”`;
}

export function moveCanvasCard(sections, { cardId, toSection, toIndex }) {
  const location = getCardLocation(sections, cardId);
  if (!location) return sections;

  if (!isMoveAllowed({ fromSection: location.sectionKey, toSection })) {
    throw new Error(`illegal move: ${location.sectionKey} -> ${toSection}`);
  }

  if (location.sectionKey === toSection) {
    return reorderCanvasCards(sections, {
      fromSection: location.sectionKey,
      toSection,
      fromIndex: location.index,
      toIndex,
    });
  }

  const sourceCards = [...sections[location.sectionKey]];
  const [movedCard] = sourceCards.splice(location.index, 1);
  const targetCards = [...sections[toSection]];
  const nextIndex = clampIndex(toIndex, targetCards.length);

  targetCards.splice(nextIndex, 0, movedCard);

  return {
    ...sections,
    [location.sectionKey]: sourceCards,
    [toSection]: targetCards,
  };
}

function clampIndex(index, length) {
  return Math.max(0, Math.min(index, length));
}
