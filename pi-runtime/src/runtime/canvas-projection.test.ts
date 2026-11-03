import { strict as assert } from "node:assert";
import { test } from "node:test";
import { renderCanvasProjection, renderHandoffSummary } from "./canvas-projection.js";
import type { ImmutableRevision } from "./workspace-revision-store.js";

test("renderCanvasProjection deterministically projects cards, relations and handoff from Revision", () => {
  const revision: ImmutableRevision = {
    revision_id: "rev-42",
    workspace_id: "ws-test",
    parent_revision_id: "rev-41",
    commit_id: "commit-42",
    created_at: new Date().toISOString(),
    change_summary: "add problem and handoff",
    actor_id: "user-1",
    objects: {
      "prob-1": {
        id: "prob-1",
        object_type: "problem",
        title: "高并发下的数据一致性",
        type_status: "initial",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      "clar-1": {
        id: "clar-1",
        object_type: "clarification",
        title: "是否需要支持跨机房容灾",
        type_status: "open",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    },
    relations: [
      {
        relation_id: "rel-1",
        source_id: "clar-1",
        target_id: "prob-1",
        relation_type: "clarifies",
      },
    ],
    confirmations: [],
    handoff: {
      status: "confirmed",
      confirmed_revision_id: "rev-42",
      updated_at: new Date().toISOString(),
    },
  };

  const checkpoint1 = renderCanvasProjection(revision, "chk-1");
  assert.equal(checkpoint1.projected_revision_id, "rev-42");
  assert.equal(checkpoint1.cards.length, 3); // 2 objects + 1 handoff card
  assert.equal(checkpoint1.relations.length, 1);
  assert.equal(checkpoint1.active_todos.length, 2);

  // 确定性重建 (Deterministic rebuild)
  const checkpoint2 = renderCanvasProjection(revision, "chk-2");
  assert.deepEqual(checkpoint1.cards, checkpoint2.cards);
  assert.deepEqual(checkpoint1.relations, checkpoint2.relations);
  assert.deepEqual(checkpoint1.active_todos, checkpoint2.active_todos);

  // 当 handoff 不是 confirmed 时，不渲染正式交接承接卡
  const draftRevision: ImmutableRevision = {
    ...revision,
    handoff: {
      status: "draft",
      updated_at: new Date().toISOString(),
    },
  };
  const draftCheckpoint = renderCanvasProjection(draftRevision);
  assert.equal(draftCheckpoint.cards.length, 2);
  assert.equal(draftCheckpoint.handoff_status, "draft");
});

test("交接按正式状态区分已完成决策与未决，并保留对象来源及确认引用", () => {
  const make = (id: string, object_type: any, type_status: string, summary: string) => ({ id, object_type, type_status, title: id, summary, created_at: "", updated_at: "", data: { source_refs: ["source-1"] }, confirmation_refs: ["confirm-1"] });
  const revision = { revision_id: "rev-test", objects: {
    rule: make("rule", "constraint", "effective", "不改审批权限"),
    decision: make("decision", "decision", "decided", "长期不填期限"),
    metrics: make("metrics", "clarification", "open", "退回率与填报成功率尚无数据"),
    closed: make("closed", "clarification", "clarified", "期限口径一致"),
  } } as unknown as ImmutableRevision;
  const summary = renderHandoffSummary(revision);
  assert.match(summary, /## 已完成决策\n- decision（已决策）/);
  assert.match(summary, /## 未决与待确认\n- metrics（待澄清）\n  退回率与填报成功率尚无数据/);
  assert.match(summary, /## 其他已记录内容\n- closed（已澄清）/);
  assert.match(summary, /结构版本：rev-test/);
  assert.match(summary, /来源 \["source-1"\]；确认 \["confirm-1"\]/);
  const projection = renderCanvasProjection({ ...revision, handoff: { status: "draft", updated_at: "" }, relations: [] });
  assert.deepEqual(projection.active_todos, ["澄清问题: metrics"]);
});
