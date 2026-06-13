"""Evoloop 3.0 契约（Contracts）的单元测试模块。

本模块主要测试核心契约层的数据模型序列化、反序列化、合法性校验、持久化机制等。
主要覆盖的测试场景包括：
- WorkItem、Playbook、ProductContext、DecisionGate、WorkerAdapter、ReviewResult 等核心对象的序列化与反序列化。
- ArtifactGraph 的完整性与依赖关系校验（检测 machine_spec 存在性、依赖循环、错误关系等）。
- Blackboard（黑板）的权限控制、动态加载、Union 类型检查和审计事件回调。
- TaskDAG 的拓扑排序、悬挂边校验、循环依赖检测及条件边属性。
- 各种模型（如 WorkItem, Playbook, ProductContext 等）在 JSON 与 YAML 格式下的文件持久化及异常处理。
"""
import unittest
from uuid import uuid4

from app.core.errors import DomainError
from app.core.subagent import (
    ExecutionMode,
    SubagentBudget,
    SubagentDenyReason,
    SubagentResult,
    SubagentRun,
    SubagentRunStatus,
    SubagentScope,
    SubagentSpawnRequest,
)
from app.core.work import WorkItem, WorkType, WorkStatus
from app.core.playbook import (
    Playbook, PlaybookStep, ProductContext, DecisionGate, WorkerAdapter,
    SourceInput, Requirement, ProductConstraint, ProductAssumption,
    KnowledgeRef, WorkerFeedback, DecisionOption, GateResolution,
    DecisionGateStatus, WorkerTargetType
)
from app.core.artifact_graph import (
    ArtifactGraph, ArtifactNode, ArtifactEdge, ArtifactRef,
    ArtifactNodeType, ArtifactEdgeType, ArtifactGraphValidationError
)
from app.core.review import (
    ReviewResult, RequirementCoverage, ReviewIssue, ReviewFixTask,
    ReviewVerdict, ReviewIssueSeverity
)
from app.services.playbook_service import PlaybookService


class TestContractsLane(unittest.TestCase):
    """契约层核心功能测试类。

    维护各类核心数据结构在各种边界场景下的业务逻辑、完整性校验、持久化和序列化测试。
    """

    def test_work_item_serialization(self):
        """测试 WorkItem 对象的字典序列化和反序列化流程。

        验证序列化生成的字典中各关键字段（如 work_type, status）的正确性，
        以及通过 from_dict 还原后的对象属性与原始对象完全一致。
        """
        item = WorkItem(
            work_type=WorkType.SPEC_TO_AGENT,
            playbook_id="playbook_123",
            title="Test Work Item",
            objective="Verify WorkItem contracts",
            workspace_id="workspace_abc",
            product_context_ref="ctx_ref_001",
            artifact_graph_ref="graph_ref_001",
            status=WorkStatus.CREATED
        )
        # 序列化为字典
        d = item.to_dict()
        self.assertEqual(d["work_type"], "spec_to_agent")
        self.assertEqual(d["status"], "created")
        self.assertEqual(d["playbook_id"], "playbook_123")
        self.assertEqual(d["iteration"], 0)
        self.assertIsNone(d["parent_work_id"])
        self.assertEqual(d["max_review_iterations"], 2)

        # 从字典反序列化还原
        item2 = WorkItem.from_dict(d)
        self.assertEqual(item2.work_id, item.work_id)
        self.assertEqual(item2.work_type, WorkType.SPEC_TO_AGENT)
        self.assertEqual(item2.title, "Test Work Item")
        self.assertEqual(item2.product_context_ref, "ctx_ref_001")
        self.assertEqual(item2.iteration, 0)
        self.assertIsNone(item2.parent_work_id)
        self.assertEqual(item2.max_review_iterations, 2)

    def test_work_item_review_iteration_fields_round_trip(self):
        """WorkItem 应持久化有界 Review-Redo Loop 所需的迭代元数据。"""
        item = WorkItem(
            work_type=WorkType.ACCEPTANCE_REVIEW,
            playbook_id="acceptance_review.compiler.pipeline.v3.enterprise",
            title="Review Billing",
            objective="Review implementation",
            workspace_id="workspace_abc",
            product_context_ref="ctx_ref_001",
            artifact_graph_ref="graph_ref_001",
            iteration=1,
            parent_work_id="task_parent",
            review_cycle_id="review_cycle_123",
            max_review_iterations=3,
        )

        data = item.to_dict()
        restored = WorkItem.from_dict(data)

        self.assertEqual(data["iteration"], 1)
        self.assertEqual(data["parent_work_id"], "task_parent")
        self.assertEqual(data["review_cycle_id"], "review_cycle_123")
        self.assertEqual(data["max_review_iterations"], 3)
        self.assertEqual(restored.iteration, 1)
        self.assertEqual(restored.parent_work_id, "task_parent")
        self.assertEqual(restored.review_cycle_id, "review_cycle_123")
        self.assertEqual(restored.max_review_iterations, 3)

    def test_subagent_run_serialization(self):
        """SubagentRun 应完整保留 scope、budget、结果与错误语义。"""
        request = SubagentSpawnRequest(
            scope=SubagentScope.SESSION_HELPER,
            goal="Inspect ambiguity",
            task_slice="Only inspect auth rule ambiguity",
            input_refs=["business_intent"],
            input_excerpt={"business_intent": "Build login with SSO"},
            allowed_tools=["knowledge.retrieve"],
            output_schema={"summary": "string", "findings": "array"},
            budget=SubagentBudget(
                max_iterations=2,
                max_input_tokens=400,
                max_output_tokens=200,
                max_tool_calls=2,
                spawn_fanout_remaining=1,
            ),
        )
        run = SubagentRun(
            parent_task_id="task_parent",
            parent_session_id="session_parent",
            root_task_id="task_root",
            scope=SubagentScope.SESSION_HELPER,
            depth=1,
            request=request,
            execution_mode=ExecutionMode.PARALLEL_HELPERS,
            status=SubagentRunStatus.DENIED,
            result=SubagentResult(
                summary="Budget gate denied helper",
                structured_output={},
                evidence_refs=[],
                used_tools=[],
                confidence="low",
                degraded=True,
                degradation_reason="input excerpt too large",
            ),
            error=DomainError("subagent.denied", "budget denied"),
            deny_reason=SubagentDenyReason.BUDGET_EXCEEDED,
        )

        data = run.to_dict()
        restored = SubagentRun.from_dict(data)

        self.assertEqual(data["scope"], "session_helper")
        self.assertEqual(data["status"], "denied")
        self.assertEqual(data["execution_mode"], "parallel_helpers")
        self.assertEqual(data["deny_reason"], "budget_exceeded")
        self.assertEqual(restored.scope, SubagentScope.SESSION_HELPER)
        self.assertEqual(restored.status, SubagentRunStatus.DENIED)
        self.assertEqual(restored.execution_mode, ExecutionMode.PARALLEL_HELPERS)
        self.assertEqual(restored.deny_reason, SubagentDenyReason.BUDGET_EXCEEDED)
        self.assertEqual(restored.request.budget.max_input_tokens, 400)

    def test_playbook_serialization(self):
        """测试 Playbook 及其内部步骤 PlaybookStep 的序列化与反序列化。

        确保 playbook 标识符、嵌套的步骤列表、工具白名单等属性在转换过程中不丢失。
        """
        step = PlaybookStep(
            step_id="step_1",
            title="Step One",
            purpose="Generate Spec",
            allowed_tools=["material.read"],
            produces_artifact_types=["machine_spec"],
            next_step_ids=["step_2"]
        )
        playbook = Playbook(
            playbook_id="playbook_v3_spec",
            version="3.0",
            trigger_types=["intent"],
            steps=[step],
            allowed_tools=["material.read", "artifact.write"],
            output_artifact_types=["machine_spec", "agent_package"]
        )
        # 执行序列化
        d = playbook.to_dict()
        self.assertEqual(d["playbook_id"], "playbook_v3_spec")
        self.assertEqual(d["steps"][0]["step_id"], "step_1")

        # 执行反序列化还原
        playbook2 = Playbook.from_dict(d)
        self.assertEqual(playbook2.playbook_id, "playbook_v3_spec")
        self.assertEqual(len(playbook2.steps), 1)
        self.assertEqual(playbook2.steps[0].title, "Step One")

    def test_product_context_serialization(self):
        """测试 ProductContext (产品上下文) 及其关联的业务对象（如需求、约束等）的序列化。

        验证包括 SourceInput、Requirement、ProductConstraint、ProductAssumption 等在内的嵌套数据结构
        是否能够正确地序列化为字典，并能成功反序列化还原。
        """
        ctx = ProductContext(
            objective="Test Objective",
            source_inputs=[SourceInput(input_id="in_1", kind="brief", summary="Brief details")],
            requirements=[Requirement(requirement_id="req_1", statement="Must support SSO")],
            constraints=[ProductConstraint(constraint_id="const_1", statement="No external DBs")],
            assumptions=[ProductAssumption(assumption_id="asmp_1", statement="Internet is up")],
            knowledge_refs=[KnowledgeRef(knowledge_id="kn_1", kind="api", summary="API spec")],
            worker_feedback=[WorkerFeedback(feedback_id="fb_1", worker_id="codex", summary="Done")]
        )
        # 执行序列化
        d = ctx.to_dict()
        self.assertEqual(d["objective"], "Test Objective")
        self.assertEqual(d["requirements"][0]["requirement_id"], "req_1")

        # 执行反序列化还原并做多级断言
        ctx2 = ProductContext.from_dict(d)
        self.assertEqual(ctx2.objective, "Test Objective")
        self.assertEqual(ctx2.requirements[0].statement, "Must support SSO")
        self.assertEqual(ctx2.constraints[0].statement, "No external DBs")
        self.assertEqual(ctx2.assumptions[0].statement, "Internet is up")

    def test_decision_gate_serialization(self):
        """测试 DecisionGate (决策网关) 及其决议 (GateResolution) 的序列化。

        验证决策选项、网关阻塞属性、状态以及最终决策方案的序列化与反序列化逻辑。
        """
        option = DecisionOption(option_id="opt_a", label="Option A", summary="Choose A")
        resolution = GateResolution(selected_option_id="opt_a", rationale="Simplest option")
        gate = DecisionGate(
            gate_id="gate_1",
            work_id="work_1",
            question="Which flow?",
            options=[option],
            impact_summary="High impact",
            blocking=True,
            status=DecisionGateStatus.OPEN,
            resolution=resolution
        )
        # 序列化
        d = gate.to_dict()
        self.assertEqual(d["gate_id"], "gate_1")
        self.assertEqual(d["resolution"]["selected_option_id"], "opt_a")

        # 反序列化
        gate2 = DecisionGate.from_dict(d)
        self.assertEqual(gate2.gate_id, "gate_1")
        self.assertEqual(gate2.options[0].label, "Option A")
        self.assertEqual(gate2.resolution.rationale, "Simplest option")

    def test_worker_adapter_serialization(self):
        """测试 WorkerAdapter (执行体适配器) 的序列化。

        校验适配器标识、目标类型、调用策略及结果接收策略在序列化前后的一致性。
        """
        adapter = WorkerAdapter(
            adapter_id="adapter_claude",
            target_type=WorkerTargetType.CLAUDE_CODE,
            package_format="markdown",
            invocation_policy={"timeout": 60},
            result_intake_policy={"format": "diff"}
        )
        # 序列化
        d = adapter.to_dict()
        self.assertEqual(d["adapter_id"], "adapter_claude")
        self.assertEqual(d["target_type"], "claude_code")

        # 反序列化
        adapter2 = WorkerAdapter.from_dict(d)
        self.assertEqual(adapter2.adapter_id, "adapter_claude")
        self.assertEqual(adapter2.target_type, WorkerTargetType.CLAUDE_CODE)
        self.assertEqual(adapter2.package_format, "markdown")

    def test_review_result_serialization(self):
        """测试 ReviewResult (验收/审查结果) 及其内部的覆盖率、缺陷列表、修复任务的序列化。

        验证验收结论（verdict）及各关联子对象的属性在序列化和反序列化中均能被完整还原。
        """
        coverage = RequirementCoverage(requirement_id="req_1", covered=True, evidence_refs=["log_1"])
        issue = ReviewIssue(issue_id="issue_1", severity=ReviewIssueSeverity.MAJOR, summary="Security leak")
        fix_task = ReviewFixTask(task_id="fix_1", title="Sanitize input", source_issue_ids=["issue_1"])
        result = ReviewResult(
            work_id="work_1",
            machine_spec_ref="spec_1",
            verdict=ReviewVerdict.CHANGES_REQUIRED,
            summary="Needs changes",
            coverage=[coverage],
            issues=[issue],
            fix_tasks=[fix_task],
            acceptance_protocol_ref="protocol_1"
        )
        # 序列化
        d = result.to_dict()
        self.assertEqual(d["verdict"], "changes_required")
        self.assertEqual(d["coverage"][0]["requirement_id"], "req_1")
        self.assertEqual(d["issues"][0]["summary"], "Security leak")
        self.assertEqual(d["fix_tasks"][0]["title"], "Sanitize input")

        # 反序列化还原
        result2 = ReviewResult.from_dict(d)
        self.assertEqual(result2.work_id, "work_1")
        self.assertEqual(result2.verdict, ReviewVerdict.CHANGES_REQUIRED)
        self.assertEqual(result2.coverage[0].covered, True)
        self.assertEqual(result2.issues[0].severity, ReviewIssueSeverity.MAJOR)
        self.assertEqual(result2.fix_tasks[0].source_issue_ids, ["issue_1"])

    def test_artifact_graph_validation_success(self):
        """测试 ArtifactGraph 在合法配置下的拓扑关系校验。

        构建包含 machine_spec（唯一真相源）、PRD 和 agent_package 的合法图结构，
        验证 graph.validate() 能够顺利通过，并能正确识别出唯一的真相源节点。
        """
        spec_ref = ArtifactRef(name="machine_spec.yaml", storage_uri="s3://specs/1")
        prd_ref = ArtifactRef(name="PRD.md", storage_uri="s3://prds/1")
        package_ref = ArtifactRef(name="package.md", storage_uri="s3://packages/1")

        spec_node = ArtifactNode(node_id="n_spec", type=ArtifactNodeType.MACHINE_SPEC, artifact_ref=spec_ref)
        prd_node = ArtifactNode(node_id="n_prd", type=ArtifactNodeType.OPTIONAL_PRD, artifact_ref=prd_ref)
        package_node = ArtifactNode(node_id="n_package", type=ArtifactNodeType.AGENT_PACKAGE, artifact_ref=package_ref)

        edge1 = ArtifactEdge(edge_id="e1", from_node_id="n_prd", to_node_id="n_spec", type=ArtifactEdgeType.DERIVES_FROM)
        edge2 = ArtifactEdge(edge_id="e2", from_node_id="n_package", to_node_id="n_spec", type=ArtifactEdgeType.DERIVES_FROM)

        graph = ArtifactGraph(
            work_id="work_1",
            nodes=[spec_node, prd_node, package_node],
            edges=[edge1, edge2]
        )
        # 应该通过校验，不抛出异常
        graph.validate()
        self.assertEqual(graph.source_of_truth_node().node_id, "n_spec")

    def test_artifact_graph_validation_no_machine_spec_with_projections(self):
        """测试 ArtifactGraph 中缺少 machine_spec 真相源时的校验拦截。

        验证当图中只存在投影节点（如 PRD）而没有 machine_spec 节点时，
        调用 validate() 会抛出 ArtifactGraphValidationError 异常。
        """
        prd_ref = ArtifactRef(name="PRD.md", storage_uri="s3://prds/1")
        prd_node = ArtifactNode(node_id="n_prd", type=ArtifactNodeType.OPTIONAL_PRD, artifact_ref=prd_ref)

        graph = ArtifactGraph(work_id="work_1", nodes=[prd_node], edges=[])
        # 验证必须且仅能包含一个 machine_spec 真相源
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph.validate()
        self.assertIn("must contain exactly one machine_spec", str(context.exception))

    def test_artifact_graph_validation_multiple_machine_specs(self):
        """测试 ArtifactGraph 中存在多个 machine_spec 真相源时的校验拦截。

        验证当图中存在两个及以上的 machine_spec 节点时，
        调用 validate() 会抛出 ArtifactGraphValidationError 异常。
        """
        spec_ref1 = ArtifactRef(name="machine_spec1.yaml")
        spec_ref2 = ArtifactRef(name="machine_spec2.yaml")

        spec_node1 = ArtifactNode(node_id="n_spec1", type=ArtifactNodeType.MACHINE_SPEC, artifact_ref=spec_ref1)
        spec_node2 = ArtifactNode(node_id="n_spec2", type=ArtifactNodeType.MACHINE_SPEC, artifact_ref=spec_ref2)

        graph = ArtifactGraph(work_id="work_1", nodes=[spec_node1, spec_node2], edges=[])
        # 验证真相源重复时的拦截
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph.validate()
        self.assertIn("must contain exactly one machine_spec", str(context.exception))

    def test_artifact_graph_validation_unconnected_projection_node(self):
        """测试 ArtifactGraph 中存在孤立投影节点时的校验拦截。

        验证当图中的投影节点（如 PRD）没有与 machine_spec 建立任何依赖连接时，
        调用 validate() 会正确检测到断联并抛出校验异常。
        """
        spec_ref = ArtifactRef(name="machine_spec.yaml")
        prd_ref = ArtifactRef(name="PRD.md")

        spec_node = ArtifactNode(node_id="n_spec", type=ArtifactNodeType.MACHINE_SPEC, artifact_ref=spec_ref)
        prd_node = ArtifactNode(node_id="n_prd", type=ArtifactNodeType.OPTIONAL_PRD, artifact_ref=prd_ref)

        # 没有边连接 prd_node 和 spec_node
        graph = ArtifactGraph(work_id="work_1", nodes=[spec_node, prd_node], edges=[])
        # 验证孤立节点拦截
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph.validate()
        self.assertIn("is disconnected from the machine_spec source of truth", str(context.exception))

    def test_artifact_graph_validation_reverse_dependence_on_projection(self):
        """测试 ArtifactGraph 中真相源错误地依赖于投影节点（逆向依赖）时的校验拦截。

        验证当 machine_spec 通过 DERIVES_FROM 错误地依赖于 PRD 时，
        调用 validate() 会拦截并报错，确保真相源不能衍生自投影产物。
        """
        spec_ref = ArtifactRef(name="machine_spec.yaml")
        prd_ref = ArtifactRef(name="PRD.md")

        spec_node = ArtifactNode(node_id="n_spec", type=ArtifactNodeType.MACHINE_SPEC, artifact_ref=spec_ref)
        prd_node = ArtifactNode(node_id="n_prd", type=ArtifactNodeType.OPTIONAL_PRD, artifact_ref=prd_ref)

        # 错误依赖：machine_spec 衍生自 prd（真相源不能衍生自投影）
        bad_edge = ArtifactEdge(
            edge_id="e_bad",
            from_node_id="n_spec",
            to_node_id="n_prd",
            type=ArtifactEdgeType.DERIVES_FROM
        )

        graph = ArtifactGraph(work_id="work_1", nodes=[spec_node, prd_node], edges=[bad_edge])
        # 校验逆向依赖拦截
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph.validate()
        self.assertIn("is invalid because the source of truth cannot derive from", str(context.exception))

    def test_artifact_graph_cycle_detection(self):
        """测试 ArtifactGraph 中存在循环依赖（环）时的校验拦截。

        构建 brief -> prd -> brief 这样的循环依赖，并与真相源连接，
        验证 validate() 能够正确检测出依赖环并抛出异常。
        """
        spec_ref = ArtifactRef(name="machine_spec.yaml")
        prd_ref = ArtifactRef(name="PRD.md")
        brief_ref = ArtifactRef(name="human_brief.md")
        
        spec_node = ArtifactNode(node_id="n_spec", type=ArtifactNodeType.MACHINE_SPEC, artifact_ref=spec_ref)
        prd_node = ArtifactNode(node_id="n_prd", type=ArtifactNodeType.OPTIONAL_PRD, artifact_ref=prd_ref)
        brief_node = ArtifactNode(node_id="n_brief", type=ArtifactNodeType.HUMAN_BRIEF, artifact_ref=brief_ref)
        
        # 形成有向循环依赖（brief -> prd -> brief）并连上 n_spec
        edge_init = ArtifactEdge(edge_id="e_init", from_node_id="n_brief", to_node_id="n_spec", type=ArtifactEdgeType.DERIVES_FROM)
        edge1 = ArtifactEdge(edge_id="e1", from_node_id="n_prd", to_node_id="n_brief", type=ArtifactEdgeType.DERIVES_FROM)
        edge2 = ArtifactEdge(edge_id="e2", from_node_id="n_brief", to_node_id="n_prd", type=ArtifactEdgeType.DERIVES_FROM)
        
        graph = ArtifactGraph(work_id="work_loop", nodes=[spec_node, prd_node, brief_node], edges=[edge_init, edge1, edge2])
        # 校验循环依赖拦截
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph.validate()
        self.assertIn("contains a dependency loop/cycle", str(context.exception))

    def test_artifact_graph_edge_type_constraints(self):
        """测试 ArtifactGraph 边类型约束（Edge Type Constraints）的组合验证。

        针对 REVIEWS、VALIDATES、ADDRESSES_REQUIREMENT、RESOLVES_DECISION 和 SUPERSEDES 等不同关系类型，
        分别验证合法的连接配置能够通过校验，而违反约束的错误配置会被 validate() 精准拦截并报错。
        """
        from app.core.artifact_graph import (
            ArtifactGraph, ArtifactNode, ArtifactEdge, ArtifactRef,
            ArtifactNodeType, ArtifactEdgeType, ArtifactGraphValidationError
        )
        
        spec_ref = ArtifactRef(name="machine_spec.yaml")
        req_ref = ArtifactRef(name="req_1")
        review_ref = ArtifactRef(name="review.md")
        decision_ref = ArtifactRef(name="dec_1")
        acceptance_ref = ArtifactRef(name="acc_1")
        checklist_ref = ArtifactRef(name="chk_1")
        
        spec_node = ArtifactNode(node_id="n_spec", type=ArtifactNodeType.MACHINE_SPEC, artifact_ref=spec_ref)
        req_node = ArtifactNode(node_id="n_req", type=ArtifactNodeType.REQUIREMENT, artifact_ref=req_ref)
        review_node = ArtifactNode(node_id="n_review", type=ArtifactNodeType.REVIEW_RESULT, artifact_ref=review_ref)
        decision_node = ArtifactNode(node_id="n_dec", type=ArtifactNodeType.DECISION, artifact_ref=decision_ref)
        acceptance_node = ArtifactNode(node_id="n_acc", type=ArtifactNodeType.ACCEPTANCE_PROTOCOL, artifact_ref=acceptance_ref)
        checklist_node = ArtifactNode(node_id="n_chk", type=ArtifactNodeType.REVIEW_CHECKLIST, artifact_ref=checklist_ref)
        
        # 1. 错误的依赖：将 reviews 边错误地从 requirement 指向 spec_node（reviews 应该从 review_result 出发）
        bad_edge = ArtifactEdge(
            edge_id="e_bad_review",
            from_node_id="n_req",
            to_node_id="n_spec",
            type=ArtifactEdgeType.REVIEWS
        )
        graph = ArtifactGraph(work_id="work_1", nodes=[spec_node, req_node], edges=[bad_edge])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph.validate()
        self.assertIn("Edge 'e_bad_review' type 'reviews' is incompatible", str(context.exception))
        
        # 2. 正确的依赖：从 review_node 指向 spec_node 应该是 reviews 关系
        good_edge = ArtifactEdge(
            edge_id="e_good_review",
            from_node_id="n_review",
            to_node_id="n_spec",
            type=ArtifactEdgeType.REVIEWS
        )
        # 应该成功，不抛出异常
        graph_ok = ArtifactGraph(work_id="work_2", nodes=[spec_node, review_node], edges=[good_edge])
        graph_ok.validate()

        # 3. VALIDATES 约束验证
        # 3a. 错误情况：VALIDATES 从 requirement 出发（VALIDATES source 必须是 acceptance_protocol 或 review_checklist）
        bad_validate_edge = ArtifactEdge(
            edge_id="e_bad_validate",
            from_node_id="n_req",
            to_node_id="n_spec",
            type=ArtifactEdgeType.VALIDATES
        )
        graph_bad_validate = ArtifactGraph(work_id="work_3a", nodes=[spec_node, req_node], edges=[bad_validate_edge])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph_bad_validate.validate()
        self.assertIn("Edge 'e_bad_validate' type 'validates' is incompatible", str(context.exception))

        # 3b. 正确情况：VALIDATES 从 acceptance_protocol 出发
        good_validate_edge_1 = ArtifactEdge(
            edge_id="e_good_validate_1",
            from_node_id="n_acc",
            to_node_id="n_spec",
            type=ArtifactEdgeType.VALIDATES
        )
        graph_good_validate_1 = ArtifactGraph(work_id="work_3b", nodes=[spec_node, acceptance_node], edges=[good_validate_edge_1])
        graph_good_validate_1.validate()

        # 3c. 正确情况：VALIDATES 从 review_checklist 出发
        good_validate_edge_2 = ArtifactEdge(
            edge_id="e_good_validate_2",
            from_node_id="n_chk",
            to_node_id="n_spec",
            type=ArtifactEdgeType.VALIDATES
        )
        graph_good_validate_2 = ArtifactGraph(work_id="work_3c", nodes=[spec_node, checklist_node], edges=[good_validate_edge_2])
        graph_good_validate_2.validate()

        # 4. ADDRESSES_REQUIREMENT 约束验证
        # 4a. 错误情况：ADDRESSES_REQUIREMENT 指向 decision 节点（ADDRESSES_REQUIREMENT target 必须是 requirement）
        bad_addr_edge = ArtifactEdge(
            edge_id="e_bad_addr",
            from_node_id="n_spec",
            to_node_id="n_dec",
            type=ArtifactEdgeType.ADDRESSES_REQUIREMENT
        )
        graph_bad_addr = ArtifactGraph(work_id="work_4a", nodes=[spec_node, decision_node], edges=[bad_addr_edge])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph_bad_addr.validate()
        self.assertIn("Edge 'e_bad_addr' type 'addresses_requirement' is incompatible", str(context.exception))

        # 4b. 正确情况：ADDRESSES_REQUIREMENT 指向 requirement
        good_addr_edge = ArtifactEdge(
            edge_id="e_good_addr",
            from_node_id="n_spec",
            to_node_id="n_req",
            type=ArtifactEdgeType.ADDRESSES_REQUIREMENT
        )
        graph_good_addr = ArtifactGraph(work_id="work_4b", nodes=[spec_node, req_node], edges=[good_addr_edge])
        graph_good_addr.validate()

        # 5. RESOLVES_DECISION 约束验证
        # 5a. 错误情况：RESOLVES_DECISION 指向 requirement 节点（RESOLVES_DECISION target 必须是 decision）
        bad_resol_edge = ArtifactEdge(
            edge_id="e_bad_resol",
            from_node_id="n_spec",
            to_node_id="n_req",
            type=ArtifactEdgeType.RESOLVES_DECISION
        )
        graph_bad_resol = ArtifactGraph(work_id="work_5a", nodes=[spec_node, req_node], edges=[bad_resol_edge])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph_bad_resol.validate()
        self.assertIn("Edge 'e_bad_resol' type 'resolves_decision' is incompatible", str(context.exception))

        # 5b. 正确情况：RESOLVES_DECISION 指向 decision
        good_resol_edge = ArtifactEdge(
            edge_id="e_good_resol",
            from_node_id="n_spec",
            to_node_id="n_dec",
            type=ArtifactEdgeType.RESOLVES_DECISION
        )
        graph_good_resol = ArtifactGraph(work_id="work_5b", nodes=[spec_node, decision_node], edges=[good_resol_edge])
        graph_good_resol.validate()

        # 6. SUPERSEDES 约束验证
        # 6a. 错误情况：SUPERSEDES 的两个节点类型不一致（一个 requirement，一个 decision）
        bad_supersedes_edge = ArtifactEdge(
            edge_id="e_bad_supersedes",
            from_node_id="n_req",
            to_node_id="n_dec",
            type=ArtifactEdgeType.SUPERSEDES
        )
        graph_bad_supersedes = ArtifactGraph(work_id="work_6a", nodes=[spec_node, req_node, decision_node], edges=[bad_supersedes_edge])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph_bad_supersedes.validate()
        self.assertIn("Edge 'e_bad_supersedes' type 'supersedes' is incompatible", str(context.exception))

        # 6b. 正确情况：SUPERSEDES 的两个节点类型一致（都是 requirement）
        req_ref_2 = ArtifactRef(name="req_2")
        req_node_2 = ArtifactNode(node_id="n_req_2", type=ArtifactNodeType.REQUIREMENT, artifact_ref=req_ref_2)
        good_supersedes_edge = ArtifactEdge(
            edge_id="e_good_supersedes",
            from_node_id="n_req_2",
            to_node_id="n_req",
            type=ArtifactEdgeType.SUPERSEDES
        )
        graph_good_supersedes = ArtifactGraph(work_id="work_6b", nodes=[spec_node, req_node, req_node_2], edges=[good_supersedes_edge])
        graph_good_supersedes.validate()

        # 7. 悬挂边 (Dangling Edge) 校验
        # 7a. from_node 不存在
        dangling_from_edge = ArtifactEdge(
            edge_id="e_dangling_from",
            from_node_id="n_non_existent",
            to_node_id="n_spec",
            type=ArtifactEdgeType.DERIVES_FROM
        )
        graph_dangling_from = ArtifactGraph(work_id="work_7a", nodes=[spec_node], edges=[dangling_from_edge])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph_dangling_from.validate()
        self.assertIn("referencing non-existent node", str(context.exception))

        # 7b. to_node 不存在
        dangling_to_edge = ArtifactEdge(
            edge_id="e_dangling_to",
            from_node_id="n_spec",
            to_node_id="n_non_existent",
            type=ArtifactEdgeType.DERIVES_FROM
        )
        graph_dangling_to = ArtifactGraph(work_id="work_7b", nodes=[spec_node], edges=[dangling_to_edge])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph_dangling_to.validate()
        self.assertIn("referencing non-existent node", str(context.exception))

    def test_playbook_service_uses_frozen_contract_field_names(self):
        """测试 PlaybookService 在启动 Playbook 时对工作项及黑板状态的处理。

        验证服务能够正确根据工作项和剧本规格初始化工作流，并确保其状态变为 RUNNING，
        同时检查其在 active_dags 和 blackboards 中均已成功注册。
        """
        item = WorkItem(
            work_type=WorkType.SPEC_TO_AGENT,
            playbook_id="playbook_v3_spec",
            title="Spec Work",
            objective="Compile intent",
            workspace_id="workspace_1",
            product_context_ref="ctx_ref_001",
            artifact_graph_ref="graph_ref_001",
        )
        playbook = Playbook(
            playbook_id="playbook_v3_spec",
            version="3.0",
            trigger_types=["intent"],
            steps=[
                PlaybookStep(
                    step_id="step_1",
                    title="Step One",
                    purpose="Generate Spec",
                    next_step_ids=["step_2"],
                )
            ],
        )

        service = PlaybookService()
        service.start_playbook(item, playbook)

        self.assertIn(item.work_id, service.active_dags)
        self.assertIn(item.work_id, service.blackboards)
        self.assertEqual(item.status, WorkStatus.RUNNING)

    def test_blackboard_slot_permission_and_type_safety(self):
        """测试 Blackboard（黑板）的权限控制与动态类型安全校验。

        验证以下业务场景：
        1. 允许的写者和读者在鉴权通过时能够正常进行读写。
        2. 写入与注册槽类型不符的数据时抛出 TypeError。
        3. 未在 allowed_writers 中的角色写入时拦截并抛出 PermissionError。
        4. 未在 allowed_readers 中的角色读取时拦截并抛出 PermissionError。
        5. 只读角色（审计节点）可以成功读取但不能进行写入。
        """
        from app.core.blackboard import Blackboard, BlackboardSlot

        blackboard = Blackboard()
        slot = BlackboardSlot(
            key="config_slot",
            data_type=dict,
            allowed_writers=["admin_node"],
            allowed_readers=["admin_node", "audit_node"]
        )
        blackboard.register_slot(slot)

        # 1. 验证正常读写
        blackboard.write("config_slot", {"theme": "dark"}, caller_id="admin_node")
        val = blackboard.read("config_slot", caller_id="admin_node")
        self.assertEqual(val, {"theme": "dark"})

        # 2. 动态类型错误拦截
        with self.assertRaises(TypeError):
            blackboard.write("config_slot", "not-a-dict", caller_id="admin_node")

        # 3. 越权写入校验
        with self.assertRaises(PermissionError):
            blackboard.write("config_slot", {"theme": "light"}, caller_id="guest_node")

        # 4. 越权读取校验
        with self.assertRaises(PermissionError):
            blackboard.read("config_slot", caller_id="guest_node")

        # 5. 审计节点可读但不可写
        val_audit = blackboard.read("config_slot", caller_id="audit_node")
        self.assertEqual(val_audit, {"theme": "dark"})
        with self.assertRaises(PermissionError):
            blackboard.write("config_slot", {"theme": "light"}, caller_id="audit_node")

    def test_task_dag_deep_validation_and_topological_sort(self):
        """测试 TaskDAG 的深度校验逻辑与拓扑排序功能。

        验证以下场景：
        1. 正常的有向无环图（DAG）能够通过校验并正确输出拓扑排序序列。
        2. 存在悬挂边（依赖了不存在的节点）时校验失败并抛出正确的错误码（dag.dangling_dependency）。
        3. 存在循环依赖（环）时校验失败并抛出正确的错误码（dag.cyclic_dependency）。
        """
        from app.core.dag import TaskDAG, DAGNode
        from app.core.errors import DomainError

        # 1. 验证正常 DAG 及其拓扑排序
        dag = TaskDAG(graph_id="normal_dag")
        node_a = DAGNode(node_id="A", action_type="agent")
        node_b = DAGNode(node_id="B", action_type="agent", dependencies=["A"])
        node_c = DAGNode(node_id="C", action_type="agent", dependencies=["B"])
        
        dag.add_node(node_a)
        dag.add_node(node_b)
        dag.add_node(node_c)

        dag.validate_dag()
        sort_order = dag.get_topological_sort()
        self.assertEqual(sort_order, ["A", "B", "C"])

        # 2. 验证悬挂边校验
        dag_dangling = TaskDAG(graph_id="dangling_dag")
        node_x = DAGNode(node_id="X", action_type="agent")
        node_y = DAGNode(node_id="Y", action_type="agent", dependencies=["Z"])
        dag_dangling.add_node(node_x)
        dag_dangling.add_node(node_y)

        with self.assertRaises(DomainError) as ctx:
            dag_dangling.validate_dag()
        self.assertEqual(ctx.exception.code, "dag.dangling_dependency")

        with self.assertRaises(DomainError) as ctx_sort:
            dag_dangling.get_topological_sort()
        self.assertEqual(ctx_sort.exception.code, "dag.dangling_dependency")

        # 3. 验证循环依赖校验
        dag_cycle = TaskDAG(graph_id="cyclic_dag")
        node_m = DAGNode(node_id="M", action_type="agent", dependencies=["N"])
        node_n = DAGNode(node_id="N", action_type="agent", dependencies=["M"])
        dag_cycle.add_node(node_m)
        dag_cycle.add_node(node_n)

        with self.assertRaises(DomainError) as ctx_cycle:
            dag_cycle.validate_dag()
        self.assertEqual(ctx_cycle.exception.code, "dag.cyclic_dependency")

        with self.assertRaises(DomainError) as ctx_cycle_sort:
            dag_cycle.get_topological_sort()
        self.assertEqual(ctx_cycle_sort.exception.code, "dag.cyclic_dependency")

    def test_strong_type_file_persistence(self):
        """测试 ProductContext 和 ArtifactGraph 强类型对象的本地文件持久化及加载。

        通过 tempfile 生成临时 JSON 文件，执行保存与加载操作，
        验证加载后的对象类型及属性字典与原始强类型对象 100% 一致。
        """
        import tempfile
        import os
        from app.core.playbook import (
            ProductContext, SourceInput, Requirement, ProductConstraint,
            ProductAssumption, KnowledgeRef, WorkerFeedback, DecisionOption,
            DecisionGate, GateResolution
        )
        from app.core.artifact_graph import (
            ArtifactGraph, ArtifactNode, ArtifactEdge, ArtifactRef,
            ArtifactNodeType, ArtifactEdgeType
        )

        # 1. 构造一个包含丰富属性的 ProductContext
        option = DecisionOption(option_id="opt_1", label="Opt 1", summary="summary opt")
        resolution = GateResolution(selected_option_id="opt_1", rationale="rat")
        gate = DecisionGate(
            gate_id="gate_1",
            work_id="work_1",
            question="Q?",
            options=[option],
            impact_summary="impact",
            resolution=resolution
        )
        ctx = ProductContext(
            objective="Test Objective",
            source_inputs=[SourceInput(input_id="in_1", kind="brief", summary="Brief details")],
            requirements=[Requirement(requirement_id="req_1", statement="Must support SSO")],
            constraints=[ProductConstraint(constraint_id="const_1", statement="No external DBs")],
            assumptions=[ProductAssumption(assumption_id="asmp_1", statement="Internet is up")],
            user_decisions=[gate],
            knowledge_refs=[KnowledgeRef(knowledge_id="kn_1", kind="api", summary="API spec")],
            worker_feedback=[WorkerFeedback(feedback_id="fb_1", worker_id="codex", summary="Done")]
        )

        # 2. 构造一个包含丰富属性的 ArtifactGraph
        spec_ref = ArtifactRef(name="machine_spec.yaml", storage_uri="s3://specs/1")
        prd_ref = ArtifactRef(name="PRD.md", storage_uri="s3://prds/1")
        spec_node = ArtifactNode(node_id="n_spec", type=ArtifactNodeType.MACHINE_SPEC, artifact_ref=spec_ref)
        prd_node = ArtifactNode(node_id="n_prd", type=ArtifactNodeType.OPTIONAL_PRD, artifact_ref=prd_ref)
        edge = ArtifactEdge(edge_id="e1", from_node_id="n_prd", to_node_id="n_spec", type=ArtifactEdgeType.DERIVES_FROM)
        
        graph = ArtifactGraph(
            work_id="work_1",
            nodes=[spec_node, prd_node],
            edges=[edge]
        )

        fd_ctx, temp_path_ctx = tempfile.mkstemp(suffix=".json")
        fd_graph, temp_path_graph = tempfile.mkstemp(suffix=".json")
        os.close(fd_ctx)
        os.close(fd_graph)

        try:
            # 持久化
            ctx.save_to_file(temp_path_ctx)
            graph.save_to_file(temp_path_graph)

            # 加载
            loaded_ctx = ProductContext.load_from_file(temp_path_ctx)
            loaded_graph = ArtifactGraph.load_from_file(temp_path_graph)

            # 断言内容 100% 一致
            self.assertEqual(ctx.to_dict(), loaded_ctx.to_dict())
            self.assertEqual(graph.to_dict(), loaded_graph.to_dict())

            # 验证类型
            self.assertIsInstance(loaded_ctx, ProductContext)
            self.assertIsInstance(loaded_graph, ArtifactGraph)

        finally:
            if os.path.exists(temp_path_ctx):
                os.remove(temp_path_ctx)
            if os.path.exists(temp_path_graph):
                os.remove(temp_path_graph)

    def test_blackboard_dynamic_loading_and_audit(self):
        """测试 Blackboard 从字典动态加载槽定义以及审计回调函数的功能。

        验证：
        1. 从包含类型、读写权限字典的列表动态解析并成功在黑板上注册槽。
        2. 注册审计回调，拦截并记录每一次正常的或越权的读写尝试，确保其记录的行为和成功标志准确无误。
        """
        from app.core.blackboard import Blackboard
        blackboard = Blackboard()
        
        # 1. 测试从字典动态加载槽定义
        slot_data = [
            {
                "key": "dynamic_int",
                "data_type": "int",
                "allowed_writers": ["writer_a"],
                "allowed_readers": ["reader_b"]
            },
            {
                "key": "dynamic_list",
                "data_type": "list",
                "allowed_writers": ["writer_c"]
            }
        ]
        blackboard.load_slots_from_dict(slot_data)
        
        # 验证是否正确解析并注册了槽
        self.assertIn("dynamic_int", blackboard._slots)
        self.assertEqual(blackboard._slots["dynamic_int"].data_type, int)
        
        # 2. 测试拦截审计回调
        audit_events = []
        def mock_audit_callback(caller_id, action, key, success, error_message=None):
            audit_events.append((caller_id, action, key, success))
            
        blackboard.set_audit_callback(mock_audit_callback)
        
        # 正常写入
        blackboard.write("dynamic_int", 42, caller_id="writer_a")
        # 越权写入
        with self.assertRaises(PermissionError):
            blackboard.write("dynamic_int", 99, caller_id="malicious_user")
            
        # 校验审计日志中记录了上述尝试
        self.assertEqual(len(audit_events), 2)
        self.assertEqual(audit_events[0], ("writer_a", "write", "dynamic_int", True))
        self.assertEqual(audit_events[1], ("malicious_user", "write", "dynamic_int", False))

    def test_blackboard_improvements(self):
        """测试 Blackboard 的多项改进机制。

        覆盖的场景包括：
        1. 匿名读写（caller_id 为 None）时自动将操作者记录为 system。
        2. 对 Union 复杂类型的兼容性，验证 Union[int, str] 能够允许整型和字符串写入但拦截浮点型。
        3. 严格模式（strict=True）下强制拦截未注册槽的读写。
        4. 验证审计回调抛出异常时，主业务流程（读写操作）不崩溃且能正常进行。
        """
        from app.core.blackboard import Blackboard, BlackboardSlot
        from typing import Union

        # 1. 测试匿名读取（caller_id=None）时，审计日志中记录 caller 为 "system"
        blackboard = Blackboard()
        audit_events = []
        def mock_audit_callback(caller_id, action, key, success, error_message=None):
            audit_events.append((caller_id, action, key, success))
        blackboard.set_audit_callback(mock_audit_callback)

        blackboard.write("some_key", "some_value")  # 默认 caller_id = None -> system
        self.assertEqual(blackboard.read("some_key"), "some_value")
        self.assertEqual(audit_events[0], ("system", "write", "some_key", True))
        self.assertEqual(audit_events[1], ("system", "read", "some_key", True))

        # 2. 测试复杂 Union 类型不崩溃且有效拦截无效类型（Union[int, str]）
        slot_union = BlackboardSlot(
            key="union_slot",
            data_type=Union[int, str]
        )
        blackboard.register_slot(slot_union)
        # 应该正常写入，不会触发 TypeError
        blackboard.write("union_slot", 42)
        blackboard.write("union_slot", "hello")
        self.assertEqual(blackboard.read("union_slot"), "hello")
        # 应该拦截无效的类型写入
        with self.assertRaises(TypeError):
            blackboard.write("union_slot", 4.5)

        # 3. 严格模式 (strict=True) 拦截未注册 slot 的读写
        strict_bb = Blackboard(strict=True)
        # 写入未注册 key 应该抛出 KeyError
        with self.assertRaises(KeyError):
            strict_bb.write("unregistered_key", "value")
        # 读取未注册 key 应该抛出 KeyError
        with self.assertRaises(KeyError):
            strict_bb.read("unregistered_key")

        # 注册后再读写则正常
        slot_ok = BlackboardSlot(key="registered_key", data_type=str)
        strict_bb.register_slot(slot_ok)
        strict_bb.write("registered_key", "value")
        self.assertEqual(strict_bb.read("registered_key"), "value")

        # 4. 测试审计回调异常不崩溃，并且不会中断主执行流
        bad_events = []
        def bad_audit_callback(caller_id, action, key, success, error_message=None):
            bad_events.append((caller_id, action, key, success))
            raise ValueError("Audit logger failed!")
        
        blackboard.set_audit_callback(bad_audit_callback)
        # 即使 audit 触发 ValueError，这里的 write 也应该成功执行，不会抛出异常
        blackboard.write("registered_key", "new_value")
        self.assertEqual(blackboard.read("registered_key"), "new_value")

    def test_task_dag_conditions_and_serialization(self):
        """测试 TaskDAG 节点的条件边属性配置及其序列化/反序列化。

        验证 DAGNode 的 conditions 条件属性能够被正确存取，并且 TaskDAG 在执行 JSON
        和 YAML 保存与重新加载后，其节点属性、依赖及条件状态依然保持完好。
        """
        from app.core.dag import TaskDAG, DAGNode, NodeStatus
        import tempfile
        import os
        
        # 1. 验证条件边属性
        node = DAGNode(
            node_id="step_conditional",
            action_type="agent",
            conditions={"blackboard.decision": "agree"}
        )
        self.assertEqual(node.conditions.get("blackboard.decision"), "agree")
        
        # 2. 验证 DAG 的 to_dict / from_dict / save_to_file / load_from_file
        dag = TaskDAG(graph_id="dag_serial_test")
        node_a = DAGNode(node_id="A", action_type="agent", status=NodeStatus.COMPLETED)
        node_b = DAGNode(
            node_id="B",
            action_type="agent",
            dependencies=["A"],
            conditions={"key": "val"}
        )
        dag.add_node(node_a)
        dag.add_node(node_b)
        
        d = dag.to_dict()
        self.assertEqual(d["graph_id"], "dag_serial_test")
        self.assertEqual(len(d["nodes"]), 2)
        self.assertEqual(d["nodes"]["B"]["dependencies"], ["A"])
        self.assertEqual(d["nodes"]["B"]["conditions"], {"key": "val"})
        
        # 文件读写 (JSON & YAML)
        fd_json, temp_path_json = tempfile.mkstemp(suffix=".json")
        fd_yaml, temp_path_yaml = tempfile.mkstemp(suffix=".yaml")
        os.close(fd_json)
        os.close(fd_yaml)
        
        try:
            # 保存 JSON 并加载
            dag.save_to_file(temp_path_json)
            loaded_dag_json = TaskDAG.load_from_file(temp_path_json)
            self.assertEqual(loaded_dag_json.graph_id, "dag_serial_test")
            self.assertEqual(loaded_dag_json.nodes["B"].conditions, {"key": "val"})
            self.assertEqual(loaded_dag_json.nodes["A"].status, NodeStatus.COMPLETED)
            
            # 保存 YAML 并加载
            dag.save_to_file(temp_path_yaml)
            loaded_dag_yaml = TaskDAG.load_from_file(temp_path_yaml)
            self.assertEqual(loaded_dag_yaml.graph_id, "dag_serial_test")
            self.assertEqual(loaded_dag_yaml.nodes["B"].conditions, {"key": "val"})
            self.assertEqual(loaded_dag_yaml.nodes["A"].status, NodeStatus.COMPLETED)
        finally:
            if os.path.exists(temp_path_json):
                os.remove(temp_path_json)
            if os.path.exists(temp_path_yaml):
                os.remove(temp_path_yaml)

    def test_contract_persistence_helpers(self):
        """综合测试各核心契约模型（WorkItem、Playbook、ProductContext 等）的持久化辅助方法。

        使用统一的临时文件清理框架，循环测试各核心对象在 JSON 与 YAML 格式下的保存与加载，
        校验保存前后的数据一致性，并验证当文件不存在或格式损坏时能正确抛出 DomainError(persistence.load_failed)。
        """
        import tempfile
        import os
        from app.core.errors import DomainError
        from app.core.work import WorkItem, WorkType, WorkStatus
        from app.core.playbook import (
            Playbook, PlaybookStep, ProductContext, SourceInput, Requirement,
            ProductConstraint, ProductAssumption, KnowledgeRef, WorkerFeedback,
            DecisionOption, DecisionGate, GateResolution
        )
        from app.core.review import (
            ReviewResult, ReviewVerdict, RequirementCoverage, ReviewIssue,
            ReviewIssueSeverity, ReviewFixTask
        )
        from app.core.dag import TaskDAG, DAGNode, NodeStatus
        from app.core.artifact_graph import (
            ArtifactGraph, ArtifactNode, ArtifactEdge, ArtifactRef,
            ArtifactNodeType, ArtifactEdgeType
        )
        
        # Helper to create temporary files and clean them up automatically
        temp_files = []
        def get_temp_path(suffix):
            fd, path = tempfile.mkstemp(suffix=suffix)
            os.close(fd)
            temp_files.append(path)
            return path

        try:
            # 1. WorkItem
            original_work_item = WorkItem(
                work_type=WorkType.SPEC_TO_AGENT,
                playbook_id="playbook_v3_spec",
                title="Spec Work",
                objective="Compile intent",
                workspace_id="workspace_1",
                product_context_ref="ctx_ref_001",
                artifact_graph_ref="graph_ref_001",
                status=WorkStatus.RUNNING
            )
            
            # 2. Playbook
            step = PlaybookStep(
                step_id="step_1",
                title="Step One",
                purpose="Generate Spec",
                allowed_tools=["material.read"],
                produces_artifact_types=["machine_spec"],
                next_step_ids=["step_2"]
            )
            original_playbook = Playbook(
                playbook_id="playbook_v3_spec",
                version="3.0",
                trigger_types=["intent"],
                steps=[step],
                allowed_tools=["material.read", "artifact.write"],
                output_artifact_types=["machine_spec", "agent_package"]
            )
            
            # 3. ProductContext
            option = DecisionOption(option_id="opt_1", label="Opt 1", summary="summary opt")
            resolution = GateResolution(selected_option_id="opt_1", rationale="rat")
            gate = DecisionGate(
                gate_id="gate_1",
                work_id="work_1",
                question="Q?",
                options=[option],
                impact_summary="impact",
                resolution=resolution
            )
            original_product_context = ProductContext(
                objective="Test Objective",
                source_inputs=[SourceInput(input_id="in_1", kind="brief", summary="Brief details")],
                requirements=[Requirement(requirement_id="req_1", statement="Must support SSO")],
                constraints=[ProductConstraint(constraint_id="const_1", statement="No external DBs")],
                assumptions=[ProductAssumption(assumption_id="asmp_1", statement="Internet is up")],
                user_decisions=[gate],
                knowledge_refs=[KnowledgeRef(knowledge_id="kn_1", kind="api", summary="API spec")],
                worker_feedback=[WorkerFeedback(feedback_id="fb_1", worker_id="codex", summary="Done")]
            )
            
            # 4. ReviewResult
            coverage = RequirementCoverage(requirement_id="req_1", covered=True, evidence_refs=["log_1"])
            issue = ReviewIssue(issue_id="issue_1", severity=ReviewIssueSeverity.MAJOR, summary="Security leak")
            fix_task = ReviewFixTask(task_id="fix_1", title="Sanitize input", source_issue_ids=["issue_1"])
            original_review_result = ReviewResult(
                work_id="work_1",
                machine_spec_ref="spec_1",
                verdict=ReviewVerdict.CHANGES_REQUIRED,
                summary="Needs changes",
                coverage=[coverage],
                issues=[issue],
                fix_tasks=[fix_task],
                acceptance_protocol_ref="protocol_1"
            )
            
            # 5. TaskDAG
            original_task_dag = TaskDAG(graph_id="dag_test")
            node_a = DAGNode(node_id="A", action_type="agent", status=NodeStatus.COMPLETED)
            node_b = DAGNode(node_id="B", action_type="agent", dependencies=["A"], conditions={"key": "val"})
            original_task_dag.add_node(node_a)
            original_task_dag.add_node(node_b)
            
            # 6. ArtifactGraph
            spec_ref = ArtifactRef(name="machine_spec.yaml", storage_uri="s3://specs/1")
            prd_ref = ArtifactRef(name="PRD.md", storage_uri="s3://prds/1")
            spec_node = ArtifactNode(node_id="n_spec", type=ArtifactNodeType.MACHINE_SPEC, artifact_ref=spec_ref)
            prd_node = ArtifactNode(node_id="n_prd", type=ArtifactNodeType.OPTIONAL_PRD, artifact_ref=prd_ref)
            edge = ArtifactEdge(edge_id="e1", from_node_id="n_prd", to_node_id="n_spec", type=ArtifactEdgeType.DERIVES_FROM)
            original_artifact_graph = ArtifactGraph(
                work_id="work_1",
                nodes=[spec_node, prd_node],
                edges=[edge]
            )

            # 测试 JSON 和 YAML 的保存与读取逻辑
            targets = [
                ("WorkItem", original_work_item, WorkItem),
                ("Playbook", original_playbook, Playbook),
                ("ProductContext", original_product_context, ProductContext),
                ("ReviewResult", original_review_result, ReviewResult),
                ("TaskDAG", original_task_dag, TaskDAG),
                ("ArtifactGraph", original_artifact_graph, ArtifactGraph),
            ]
            
            for name, original_obj, cls in targets:
                for ext in [".json", ".yaml"]:
                    path = get_temp_path(ext)
                    original_obj.save_to_file(path)
                    loaded_obj = cls.load_from_file(path)
                    self.assertEqual(
                        loaded_obj.to_dict(), 
                        original_obj.to_dict(),
                        f"Mismatch after saving/loading {name} with extension {ext}"
                    )
            
            # 7. 验证加载不存在文件时抛出异常
            non_existent_path = "/non_existent_dir/no_file.json"
            with self.assertRaises(DomainError) as context_none:
                WorkItem.load_from_file(non_existent_path)
            self.assertEqual(context_none.exception.code, "persistence.load_failed")
            
            # 8. 验证加载损坏的文件时抛出异常
            invalid_content_path = get_temp_path(".yaml")
            with open(invalid_content_path, "w", encoding="utf-8") as f:
                f.write("invalid: [unclosed bracket")
                
            with self.assertRaises(DomainError) as context_invalid:
                WorkItem.load_from_file(invalid_content_path)
            self.assertEqual(context_invalid.exception.code, "persistence.load_failed")

        finally:
            # 清理临时生成的文件
            for path in temp_files:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass


if __name__ == "__main__":
    unittest.main()
