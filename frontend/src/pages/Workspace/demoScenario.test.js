/**
 * @file demoScenario.test.js
 * @description 约束 EvoCanvas 演示场景数据的完整性，确保对话、画布与结构化交接物覆盖完整闭环。
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import {
  DEMO_CANVAS_SECTIONS,
  DEMO_CHAT,
  DEMO_DOC,
  DEMO_DOC_SECONDARY,
  PLACEHOLDER_NAMES,
} from './demoScenario.js';

test('demo scenario covers every canvas stage with non-empty cards', () => {
  const requiredSections = ['evidence', 'problems', 'clarify', 'rules', 'planning'];

  for (const section of requiredSections) {
    assert.ok(Array.isArray(DEMO_CANVAS_SECTIONS[section]), `${section} should be an array`);
    assert.ok(DEMO_CANVAS_SECTIONS[section].length > 0, `${section} should contain cards`);
  }

  const allCards = Object.values(DEMO_CANVAS_SECTIONS).flat();
  assert.ok(allCards.length >= 10, 'demo canvas should feel like a complete project, not a skeleton');

  for (const card of allCards) {
    const structuredFragments = (card.structuredItems || []).map((item) =>
      typeof item === 'string' ? item : `${item.label}${item.text}`,
    );
    const textFragments = [
      card.title,
      card.desc,
      ...structuredFragments,
      ...(card.attachments || []).map((attachment) => attachment.label),
      card.owner?.name,
      card.source?.name,
    ].filter(Boolean);

    assert.ok(card.id, 'every card should have an id');
    assert.ok(card.title, `card ${card.id} should have a title`);
    assert.ok(
      textFragments.join('').trim().length >= 12,
      `card ${card.id} should carry meaningful content instead of a bare structure`,
    );
  }
});

test('demo canvas uses unified persona metadata and confidence instead of star ratings', () => {
  const allCards = Object.values(DEMO_CANVAS_SECTIONS).flat();
  const evidenceCards = DEMO_CANVAS_SECTIONS.evidence;
  const clarifyCards = DEMO_CANVAS_SECTIONS.clarify;
  const ruleCards = DEMO_CANVAS_SECTIONS.rules;
  const planningCards = DEMO_CANVAS_SECTIONS.planning;

  for (const card of allCards) {
    if (card.source) {
      assert.ok(card.source.avatarTone, `source on ${card.id} should declare an avatar tone`);
      assert.ok(card.source.avatarSrc, `source on ${card.id} should declare an avatar source`);
    }

    if (card.owner) {
      assert.ok(card.owner.avatarTone, `owner on ${card.id} should declare an avatar tone`);
      assert.ok(card.owner.avatarSrc, `owner on ${card.id} should declare an avatar source`);
    }
  }

  for (const card of evidenceCards) {
    assert.equal('rating' in card, false, `evidence card ${card.id} should not use star ratings`);
    assert.equal(typeof card.confidence, 'number', `evidence card ${card.id} should expose confidence`);
    assert.ok(card.confidence >= 0 && card.confidence <= 100, `confidence on ${card.id} should be a percentage`);
    assert.equal(card.structureKind, 'quote', `evidence card ${card.id} should use quote structure`);
  }

  for (const card of clarifyCards) {
    assert.equal(card.structureKind, 'list', `clarify card ${card.id} should use list structure`);
  }

  for (const card of [...ruleCards, ...planningCards]) {
    assert.equal(card.structureKind, 'checkpoints', `${card.id} should use checkpoints structure`);
  }
});

test('demo scenario uses realistic names instead of placeholder names', () => {
  const textCorpus = [
    DEMO_DOC,
    DEMO_DOC_SECONDARY,
    ...DEMO_CHAT.map((message) => message.text),
    ...Object.values(DEMO_CANVAS_SECTIONS).flatMap((card) => [
      card.title,
      card.desc,
      card.owner?.name,
      card.source?.name,
      ...(card.structuredItems || []).map((item) =>
        typeof item === 'string' ? item : `${item.label}${item.text}`,
      ),
      ...(card.attachments || []).map((attachment) => attachment.label),
    ]),
  ]
    .filter(Boolean)
    .join('\n');

  for (const name of PLACEHOLDER_NAMES) {
    assert.equal(
      textCorpus.includes(name),
      false,
      `demo scenario should not contain placeholder name: ${name}`,
    );
  }
});

test('demo chat and handoff document describe the EvoCanvas 1.0 workflow', () => {
  assert.ok(DEMO_CHAT.length >= 10, 'demo chat should show a real multi-turn collaboration');
  assert.match(DEMO_DOC, /待澄清问题/u);
  assert.match(DEMO_DOC, /约束/u);
  assert.match(DEMO_DOC, /待决策/u);
  assert.match(DEMO_DOC_SECONDARY, /输入编译/u);
  assert.ok(
    DEMO_CHAT.some((message) => /已在画布/u.test(message.text)),
    'demo chat should explicitly mention how the agent updates the canvas',
  );
});
