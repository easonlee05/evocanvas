import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { buildAiPrdMarkdown, normalizeHandoffView } from './handoffExport.js';

describe('handoffExport', () => {
  it('normalizes outdated/invalidated statuses and preserves stale reason', () => {
    const view = normalizeHandoffView(
      {
        status: 'invalidated',
        handoff: {
          revision_id: 'rev_abcdef1234567890',
          stale_reason: '约束 C-01 已更新',
          summary: '旧交接摘要',
        },
      },
      [{ kind: 'clarification', status: 'open', title: '确认阈值' }],
    );

    assert.equal(view.status, 'outdated');
    assert.equal(view.statusLabel, '已过时');
    assert.equal(view.isOutdated, true);
    assert.equal(view.canPublishToKnowledge, false);
    assert.equal(view.staleReason, '约束 C-01 已更新');
    assert.equal(view.openGapCount, 1);
  });

  it('allows publishing to knowledge base only when handoff is confirmed', () => {
    const draftView = normalizeHandoffView({ status: 'draft', handoff: { summary: '草稿内容' } });
    assert.equal(draftView.canPublishToKnowledge, false);

    const confirmedView = normalizeHandoffView({ status: 'confirmed', handoff: { summary: '已确认交接内容' } });
    assert.equal(confirmedView.isConfirmed, true);
    assert.equal(confirmedView.canPublishToKnowledge, true);
  });

  it('derives AI PRD separating confirmed constraints from open boundaries', () => {
    const cards = [
      { kind: 'problem', title: '大促误触率高', summary: '活动页弹窗频繁误触', status: 'confirmed' },
      { kind: 'constraint', title: '不改动现有结算链路', summary: '零侵入', status: 'confirmed' },
      { kind: 'decision', title: '采用二次确认弹窗', summary: '仅高价值券触发', status: 'confirmed' },
      { kind: 'decision', title: '是否灰度 10%', summary: '待运营拍板', status: 'pending' },
      { kind: 'clarification', title: '客服兜底 SLA 是多久', summary: '未答复', status: 'open' },
      { kind: 'evidence', title: '618 客诉周报', summary: '误触占比 32%' },
    ];
    const view = normalizeHandoffView({ status: 'confirmed', handoff: { version: 2, summary: '核心收敛摘要' } }, cards);
    const md = buildAiPrdMarkdown({
      title: '618 误触治理',
      workspaceId: 'ws_618',
      handoffView: view,
      cards,
    });

    assert.match(md, /# 618 误触治理 — 面向 AI 的结构化需求交接/);
    assert.match(md, /## 4\. 已确认约束（必须遵守）[\s\S]*不改动现有结算链路/);
    assert.match(md, /## 5\. 已完成决策[\s\S]*采用二次确认弹窗/);
    assert.match(md, /## 6\. 仍未决边界（严禁下游 AI 自行脑补）[\s\S]*客服兜底 SLA 是多久[\s\S]*是否灰度 10%/);
    assert.match(md, /## 7\. 关键背景与来源证据[\s\S]*618 客诉周报/);
  });
});
