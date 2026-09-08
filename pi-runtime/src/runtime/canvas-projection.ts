import type { ImmutableRevision } from "./workspace-revision-store.js";

export interface CanvasCardProjection {
  card_id: string;
  card_type: "evidence" | "problem" | "clarification" | "constraint" | "decision" | "handoff";
  stage: "discovery" | "define" | "handoff";
  title: string;
  type_status: string;
  summary?: string;
  confirmation_refs?: string[];
  created_at: string;
  updated_at: string;
}

export interface CanvasRelationProjection {
  relation_id: string;
  source_card_id: string;
  target_card_id: string;
  relation_type: string;
}

export interface CanvasProjectionCheckpoint {
  checkpoint_id: string;
  workspace_id: string;
  projected_revision_id: string;
  cards: CanvasCardProjection[];
  relations: CanvasRelationProjection[];
  active_todos: string[];
  handoff_status: string;
  rendered_at: string;
}

function mapCardStage(cardType: CanvasCardProjection["card_type"]): CanvasCardProjection["stage"] {
  switch (cardType) {
    case "evidence":
      return "discovery";
    case "problem":
    case "clarification":
    case "constraint":
    case "decision":
      return "define";
    case "handoff":
      return "handoff";
  }
}

/**
 * 确定性从不可变 Revision 渲染 Canvas 投影
 */
export function renderCanvasProjection(
  revision: ImmutableRevision,
  checkpointId?: string,
): CanvasProjectionCheckpoint {
  const cards: CanvasCardProjection[] = [];
  const activeTodos: string[] = [];

  for (const obj of Object.values(revision.objects)) {
    const cardType = obj.object_type as CanvasCardProjection["card_type"];
    const stage = mapCardStage(cardType);

    cards.push({
      card_id: obj.id,
      card_type: cardType,
      stage,
      title: obj.title,
      type_status: obj.type_status,
      summary: obj.summary,
      confirmation_refs: obj.confirmation_refs,
      created_at: obj.created_at,
      updated_at: obj.updated_at,
    });

    if (cardType === "problem" && obj.type_status !== "resolved") {
      activeTodos.push(`解决焦点问题: ${obj.title}`);
    } else if (cardType === "clarification" && obj.type_status !== "answered") {
      activeTodos.push(`澄清问题: ${obj.title}`);
    } else if (cardType === "decision" && obj.type_status === "pending") {
      activeTodos.push(`待决策事项: ${obj.title}`);
    }
  }

  // 若存在 handoff 状态且有 confirmed_revision_id，显影交接承接卡
  if (revision.handoff && revision.handoff.status === "confirmed") {
    cards.push({
      card_id: `card_handoff_${revision.handoff.confirmed_revision_id}`,
      card_type: "handoff",
      stage: "handoff",
      title: `结构化交接包 [${revision.handoff.confirmed_revision_id}]`,
      type_status: revision.handoff.status,
      summary: `已确认交接物版本，对应 Revision ${revision.handoff.confirmed_revision_id}`,
      created_at: revision.handoff.updated_at,
      updated_at: revision.handoff.updated_at,
    });
  }

  const relations: CanvasRelationProjection[] = revision.relations.map((rel) => ({
    relation_id: rel.relation_id,
    source_card_id: rel.source_id,
    target_card_id: rel.target_id,
    relation_type: rel.relation_type,
  }));

  return {
    checkpoint_id: checkpointId || `chk_${Date.now()}`,
    workspace_id: revision.workspace_id,
    projected_revision_id: revision.revision_id,
    cards,
    relations,
    active_todos: activeTodos,
    handoff_status: revision.handoff.status,
    rendered_at: new Date().toISOString(),
  };
}

/** 交接正文按确认版本派生；包括全部未决与风险，不保存独立可编辑正文。 */
export function renderHandoffSummary(revision: ImmutableRevision): string {
  const labels: Record<string,string> = {evidence:"来源证据",problem:"问题",clarification:"待澄清",constraint:"约束",decision:"待决策",handoff:"交接"};
  return Object.values(revision.objects).map(obj => `- ${labels[obj.object_type] || obj.object_type}：${obj.title}（${obj.type_status}）${obj.summary ? `\n  ${obj.summary}` : ""}${obj.data?.risks ? `\n  风险：${JSON.stringify(obj.data.risks)}` : ""}`).join("\n");
}
