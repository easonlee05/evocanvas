/**
 * @file canvasEditing.test.js
 * @description 针对画布卡片编辑与迁移规则的单元测试，确保行为符合 EvoCanvas 1.0 PRD。
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { DEMO_CANVAS_SECTIONS } from './demoScenario.js';
import {
  createInitialCanvasSections,
  getCardLocation,
  isMoveAllowed,
  moveCanvasCard,
  reorderCanvasCards,
  updateCanvasCard,
} from './canvasEditing.js';

test('updateCanvasCard updates only title and desc fields in place', () => {
  const sections = createInitialCanvasSections(DEMO_CANVAS_SECTIONS);
  const nextSections = updateCanvasCard(sections, 'p1', {
    title: '618 积分发放链路治理（一期）',
    desc: '聚焦邀请返积分与签到补签，不扩展到全站任务体系。',
  });
  const updatedCard = nextSections.problems.find((card) => card.id === 'p1');

  assert.equal(updatedCard.title, '618 积分发放链路治理（一期）');
  assert.equal(updatedCard.desc, '聚焦邀请返积分与签到补签，不扩展到全站任务体系。');
  assert.equal(updatedCard.statusPill.label, '范围已聚焦');
});

test('reorderCanvasCards reorders cards inside the same section only', () => {
  const sections = createInitialCanvasSections(DEMO_CANVAS_SECTIONS);
  const reordered = reorderCanvasCards(sections, {
    fromSection: 'evidence',
    toSection: 'evidence',
    fromIndex: 0,
    toIndex: 2,
  });

  assert.deepEqual(
    reordered.evidence.map((card) => card.id),
    ['e2', 'e3', 'e1'],
  );
});

test('isMoveAllowed only permits PRD-aligned forward migrations', () => {
  assert.equal(isMoveAllowed({ fromSection: 'evidence', toSection: 'problems' }), true);
  assert.equal(isMoveAllowed({ fromSection: 'clarify', toSection: 'rules' }), true);
  assert.equal(isMoveAllowed({ fromSection: 'rules', toSection: 'planning' }), true);
  assert.equal(isMoveAllowed({ fromSection: 'evidence', toSection: 'planning' }), false);
  assert.equal(isMoveAllowed({ fromSection: 'planning', toSection: 'clarify' }), false);
});

test('moveCanvasCard moves a card into a legal target section and keeps data intact', () => {
  const sections = createInitialCanvasSections(DEMO_CANVAS_SECTIONS);
  const moved = moveCanvasCard(sections, {
    cardId: 'c3',
    toSection: 'rules',
    toIndex: 1,
  });
  const movedCard = moved.rules[1];

  assert.equal(movedCard.id, 'c3');
  assert.equal(getCardLocation(moved, 'c3').sectionKey, 'rules');
  assert.equal(movedCard.title, '申诉 SLA 由谁兜底，是否要求 T+0 完成');
});

test('moveCanvasCard rejects illegal target sections and preserves original placement', () => {
  const sections = createInitialCanvasSections(DEMO_CANVAS_SECTIONS);

  assert.throws(
    () =>
      moveCanvasCard(sections, {
        cardId: 'e1',
        toSection: 'planning',
        toIndex: 0,
      }),
    /illegal move/u,
  );
  assert.equal(getCardLocation(sections, 'e1').sectionKey, 'evidence');
});
