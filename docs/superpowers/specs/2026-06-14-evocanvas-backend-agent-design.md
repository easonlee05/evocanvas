# EvoCanvas Backend + Agent Design

> Status: Draft in active review
> Last Updated: 2026-06-14
> Scope: EvoCanvas 1.0 backend refactor, with first priority on Canvas and Agent capabilities
> Collaboration mode: This document is intended to be updated incrementally as product and implementation decisions are approved

## 1. Background

EvoCanvas 1.0 is not a PRD generator and not a generic whiteboard. The backend must serve the 1.0 product loop defined in [docs/vision/EvoCanvas1.0-PRD.md](/Users/apple/Desktop/evocanvas/docs/vision/EvoCanvas1.0-PRD.md):

`input compilation -> clarifications -> constraints / decisions -> structured handoff`

The current frontend has already been refactored toward the EvoCanvas shape, but the backend still carries strong Evoloop semantics such as:

- `manual-agent-phase1`
- `legacy_manual` / `legacy_prd`
- `machine_spec` as the center of truth
- peer delivery flows designed around spec/review outputs

At the same time, the repository already contains reusable infrastructure that should not be discarded:

- task lifecycle
- event bus and SSE streaming
- bounded `AgentSession`
- governed `Subagent`
- arbitration / `DecisionGate`
- storage, context, artifact and session plumbing

The backend refactor should therefore be a semantically focused migration, not a full rewrite.

## 2. Confirmed Direction

The following product and architecture decisions are already confirmed:

### 2.1 Delivery level

The first backend milestone should reach:

- real Canvas backend
- real Agent backend
- editable Canvas support

This corresponds to:

- no longer relying on static demo Canvas data as the system source
- supporting low-risk automatic updates from the agent
- supporting high-impact changes through explicit user confirmation

### 2.2 Agent strategy

The agent should use:

- one visible assistant in the frontend
- multiple internal roles in the backend

This means the user sees a single `Canvas AI`, while the backend internally orchestrates specialized roles.

### 2.3 Subagent reuse

The existing Evoloop `subagent` model should be reused where it matches EvoCanvas needs.

Confirmed reuse principle:

- keep `subagent` as an internal governed execution primitive
- do not keep old spec-centric product semantics as the new product center

### 2.4 Mutation governance

The default write policy is:

- low-risk changes can be auto-applied
- high-impact changes must require confirmation

This is the operating policy for EvoCanvas 1.0 agent behavior.

## 3. Chosen Architecture

The backend should be organized into four cooperating layers.

### 3.1 Canvas Domain

This is the new EvoCanvas-native core domain. It replaces the old document/spec-centered product semantics as the primary truth layer for 1.0.

Responsibilities:

- represent the current workspace state
- represent Canvas cards and relations
- represent snapshots and Todo projections
- represent structured handoff state
- represent agent-proposed mutations before they are applied

This layer should become the product truth source for EvoCanvas 1.0.

### 3.2 Canvas Agent Orchestrator

This layer powers the single visible `Canvas AI`.

Responsibilities:

- receive user input and current workspace context
- recognize the current intent
- dispatch internal agent roles
- collect role outputs
- merge them into one governed mutation proposal

The orchestrator should reuse the existing bounded `AgentSession` and `SubagentService` ideas, but redirect them from spec delivery toward Canvas evolution.

### 3.3 Mutation Governance

This layer determines whether proposed changes:

- apply automatically
- require user confirmation
- should be rejected and turned into a follow-up question

This is the productized form of the old arbitration and decision gate capability.

### 3.4 Delivery API + Event Stream

This layer serves the frontend and publishes Canvas-native events.

Responsibilities:

- expose workspace and Canvas state
- expose pending confirmations
- apply approved mutations
- serve snapshots and handoff state
- stream agent and Canvas events via SSE

## 4. Core Domain Model

The backend should not let agents directly mutate arbitrary frontend JSON. Instead, it should define EvoCanvas-native domain objects and let agents emit structured mutation sets.

### 4.1 CanvasWorkspace

Represents one PM working context.

Suggested responsibilities:

- workspace identity
- title and current objective
- linked source inputs
- current active snapshot id
- active handoff state
- metadata for current agent session and view state

### 4.2 CanvasCard

Unified card model for EvoCanvas 1.0. Card types should stay within 1.0 scope:

- `evidence`
- `problem`
- `clarification`
- `constraint`
- `decision`
- `handoff`

Each card should support at least:

- stable id
- title
- summary
- card type
- stage / module placement
- draft / active / resolved / superseded style status
- source refs
- confirmation metadata when applicable

### 4.3 CanvasRelation

High-value relation set only. Proposed relation types:

- `derived_from`
- `clarifies`
- `supports`
- `blocks`
- `conflicts_with`
- `produces`

This keeps the graph useful without turning the Canvas into an uncontrolled network map.

### 4.4 CanvasSnapshot

Snapshots are not full database copies. A snapshot should represent the effective cognitive state at a meaningful moment.

Each snapshot should capture:

- active card ids
- effective card states
- active relations
- Todo projection
- summary of key changes
- business-facing snapshot title

### 4.5 TodoProjection

Todo is not a source of truth. It is derived from active gaps in the Canvas.

Its inputs should primarily come from:

- open clarification cards
- pending decision cards
- draft but not confirmed constraints

### 4.6 StructuredHandoff

The handoff should exist both as:

- a visible `handoff` card on the Canvas
- a structured body that can be reused by future sessions or other agents

Suggested minimum fields:

- objective
- background inputs
- confirmed constraints
- open questions
- pending decisions
- recommended next actions
- source snapshot id

### 4.7 CanvasMutation

This is the core execution unit for agent-driven changes.

Suggested mutation types:

- `add_card`
- `update_card_summary`
- `update_card_title`
- `mark_conflict`
- `add_relation`
- `move_card_stage`
- `promote_to_constraint_draft`
- `confirm_constraint`
- `create_decision_request`
- `resolve_clarification`
- `refresh_handoff_draft`
- `create_snapshot`

### 4.8 MutationProposal

A proposal groups one batch of agent-produced mutations and makes it governable.

Each proposal should include:

- proposal id
- originating message / turn id
- involved internal roles
- list of proposed mutations
- evidence refs
- rationale summary
- risk level
- whether confirmation is required

## 5. Why Mutation-First Instead Of Direct Write

This design choice is central.

The agent should not directly rewrite the Canvas state as its first output. Instead, it should always produce `CanvasMutation` objects first.

Reasons:

- it preserves explainability
- it allows risk-aware governance before write
- it supports snapshot and diff generation
- it keeps user confirmation traceable
- it avoids silently turning ambiguous inputs into stable state

This directly supports the EvoCanvas 1.0 principle:

`expose uncertainty first, then settle constraints, then form decisions, then generate handoff`

## 6. Agent Strategy

The chosen agent strategy is:

- one visible assistant
- several internal specialist roles
- one orchestrating supervisor

### 6.1 Visible agent

Frontend only sees:

- one conversation
- one assistant identity
- one stream of summary and confirmation prompts

### 6.2 Internal roles

The backend should begin with five fixed internal roles.

#### Input Compiler

Responsibilities:

- ingest new input
- extract evidence
- form initial problem statements
- propose first-pass clarification items

#### Clarifier

Responsibilities:

- detect ambiguity
- detect missing context
- detect conflicts across inputs
- prefer clarification over premature conclusion

#### Constraint Steward

Responsibilities:

- identify stable boundaries
- propose draft constraints
- never mark constraints as effective by default

#### Decision Steward

Responsibilities:

- identify when something is not missing information but missing human judgment
- create decision candidates with options and impact framing

#### Handoff Builder

Responsibilities:

- synthesize current structured handoff draft
- include unresolved gaps instead of pretending closure

### 6.3 Orchestrator responsibilities

The `Canvas Supervisor` should:

- determine current user intent
- choose which internal roles to run
- define the allowed mutation range for this turn
- merge internal role outputs into one proposal
- escalate conflicts into clarification or decision objects instead of silently flattening them

## 7. Agent Execution Flow

For each user turn, the backend should follow this sequence.

### 7.1 Input loading

Load:

- workspace state
- active snapshot
- selected cards if any
- recent conversation
- relevant source inputs

### 7.2 Intent recognition

Classify the turn into one or more EvoCanvas intents:

- input compilation
- clarification
- constraint shaping
- decision surfacing
- handoff convergence

### 7.3 Internal subagent dispatch

Run only the internal roles needed for this turn.

Important execution rule:

- internal roles do not directly write storage
- internal roles only return structured outputs

### 7.4 Structured outputs

Each internal role should return a schema-shaped result including:

- findings
- proposed mutations
- evidence refs
- confidence
- open questions
- requires human confirmation

### 7.5 Supervisor merge

Supervisor merges role results into a single `MutationProposal`.

When role outputs conflict:

- do not silently merge
- create or update clarification state
- escalate to decision state when human judgment is required

### 7.6 Governance decision

The proposal is sent through risk-aware mutation governance.

Possible outcomes:

- auto-apply
- confirmation-required
- ask-follow-up-without-write

### 7.7 Persistence and event emission

After governance:

- approved low-risk mutations are written
- high-impact mutations become pending confirmation objects
- events are emitted for frontend sync

## 8. Governance Policy

This section reflects the confirmed default product policy.

### 8.1 Auto-apply examples

Suggested low-risk auto-applied mutations:

- add evidence card
- add or enrich problem description
- add clarification card
- mark conflict between inputs
- enrich handoff draft wording
- refresh Todo projection

### 8.2 Confirmation-required examples

Suggested high-impact mutations requiring explicit confirmation:

- convert clarification into confirmed constraint
- mark a constraint as effective
- resolve a key clarification as closed
- finalize a decision outcome
- create a key snapshot
- overwrite or promote a formal handoff state
- perform major stage migration for important cards

### 8.3 Ask-without-write cases

The agent should not mutate the Canvas when:

- evidence is insufficient
- internal role results materially conflict
- the user input is too ambiguous to classify safely

In such cases, the system should respond with a follow-up question and explicitly state that no Canvas mutation was applied.

## 9. Reuse Map From Existing Evoloop Infrastructure

The goal is to preserve good infrastructure while replacing old product semantics.

### 9.1 Keep and reuse

- `TaskService` as a control-plane base
- `Event` and `EventBus`
- SSE endpoint pattern
- `AgentSession`
- `AgentRuntime`
- `SubagentService`
- budget / tool policy / schema-governed internal execution
- existing storage and session plumbing

### 9.2 Reinterpret and adapt

- `DecisionGate` becomes the engine behind EvoCanvas confirmation and decision flows
- graph ideas from `ArtifactGraph` inform `CanvasCard + CanvasRelation`, but `ArtifactGraph` should not remain the product truth source
- `ProductContext` ideas can be absorbed into `StructuredHandoff` and workspace context

### 9.3 De-emphasize from the 1.0 main path

- `machine_spec` as center of truth
- `legacy_manual` / `legacy_prd` semantics
- peer delivery package as the core product output
- formal spec/review loop as the primary product loop

### 9.4 Keep available but not central

Existing formal subtask and peer collaboration flows can remain in the codebase as reusable infrastructure, but they should not define EvoCanvas 1.0 user-facing semantics.

## 10. API Direction

The detailed API contract is still pending, but the backend should move toward Canvas-native endpoints rather than using static demo data.

Expected API groups:

- workspace read
- Canvas state read
- message / agent turn submission
- mutation confirmation / rejection
- snapshot listing and switching
- handoff retrieval
- Todo projection retrieval

Existing `/api/tasks/*` endpoints and SSE flows can be used as migration scaffolding, but the public contract should gradually become EvoCanvas-native.

## 11. Event Direction

Frontend-facing events should evolve toward Canvas semantics.

Suggested event families:

- `agent.intent.recognized`
- `subagent.run.started`
- `subagent.run.completed`
- `canvas.mutation.proposed`
- `canvas.mutation.applied`
- `canvas.confirmation.requested`
- `canvas.snapshot.created`
- `handoff.refreshed`

These events will allow the frontend to stop depending on hardcoded demo behavior.

## 12. Current Gaps And Pending Sections

The following design sections are not yet fully specified and should be added as future review rounds are approved:

- exact file/module layout for the new backend code
- migration path from current `/api/tasks/*` to EvoCanvas-native APIs
- detailed schema definitions for `CanvasCard`, `CanvasMutation`, `MutationProposal`, and snapshots
- persistence model and storage layout
- snapshot generation rules and diff algorithm
- Todo projection rules
- confirmation queue representation
- testing strategy
- step-by-step implementation plan

## 13. Recommended Next Design Sections

The next review rounds should cover, in order:

1. backend module split and file ownership
2. API contract and SSE contract
3. persistence model and storage format
4. workflow wiring on top of existing task/session infrastructure
5. confirmation model and mutation risk classifier
6. tests and migration rollout

## 14. Change Log

### 2026-06-14

- recorded the confirmed decision to target editable real Canvas plus real agent support
- recorded the confirmed choice of a single visible assistant with internal multi-role orchestration
- recorded the confirmed decision to reuse Evoloop subagent concepts as internal governed execution
- recorded the confirmed governance policy of low-risk auto-apply and high-impact confirmation
- documented the agreed architecture, domain model, agent flow, and reuse strategy
