"""
Evoloop 后端 Phase 1 核心功能集成测试模块。

本模块涵盖了 Evoloop 3.0 的基础后端核心链路集成测试，测试对象涉及：
1. 默认注册表（build_task_registry）中的 spec_to_agent 和 acceptance_review 等 3.0 原生 Playbook 注册。
2. TaskService 对原生任务的创建与运行，以及对应的 FastAPi 路由挂载和请求承载。
3. 产品上下文（ProductContext）和 MCP 接口中对原始业务意图（Requirements）的格式化与序列化。
4. 原生产物图（Artifact Graph）节点类型（如 machine_spec, agent_package 等）的流转正确性验证。
5. 任务工作项列表 API (/api/work-items) 的租户和历史演进数据渲染。
6. 工作流执行中的计时元数据（duration_ms）、遥测（LLM Telemetry）脱敏记录以及人工裁决（arbitration）的暂停和恢复。
7. 检查点（checkpoint）机制在重新载入服务时的重放恢复流程。
8. 权限白名单（Tool Policy）的严格过滤与报错。
9. 产物写入（artifact.write）操作的逻辑幂等性校验。
10. 自定义评审（Reviewer）异常输出对门控安全校验的防误判保护。
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import json

from fastapi.testclient import TestClient

from app.api.server import build_default_task_service, create_app
from app.core.artifact_graph import ArtifactNodeType
from app.core.ports import LLMResult
from app.core.task import TaskStatus
from app.core.tools import ToolCall
from app.services.fakes import FakeKnowledge, FakeLLM, FakeStorage
from app.services.peer_adapter_service import PeerAdapterService
from app.services.task_service import TaskService
from app.services.tool_service import ToolService
from app.workflows.definitions import build_task_registry
from app.workflows.engine import WorkflowEngine
from app.mcp.tools import register_tools


class BackendPhase1Tests(unittest.TestCase):
    """
    后端 Phase 1 核心功能的集成测试类。

    维护了一个标准的轻量级微服务（TaskService, FakeStorage, ToolService）套件，
    用于验证多端联调及后端流程的核心保障指标。
    """

    def make_service(self):
        """
        构建供测试环境使用的临时 TaskService 及其配套依赖。

        Returns:
            tuple: (TaskService 实例, FakeStorage 实例, ToolService 实例)
        """
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        registry = build_task_registry()
        storage = FakeStorage(root)
        tool_service = ToolService.default(root=root, knowledge=FakeKnowledge())
        engine = WorkflowEngine(tool_service=tool_service, llm=FakeLLM(), storage=storage)
        service = TaskService(
            registry=registry,
            engine=engine,
            storage=storage,
            peer_adapter=PeerAdapterService(),
        )
        # 注册清理回调，防止临时文件残留
        self.addCleanup(temp.cleanup)
        return service, storage, tool_service

    def test_default_registry_exposes_native_3_0_playbooks(self):
        """
        验证默认的 Playbook 注册表中是否正确暴露了 Evoloop 3.0 的核心工作流。

        断言：
        - 包含 spec_to_agent 工作流。
        - 包含 acceptance_review 工作流。
        """
        registry = build_task_registry()

        self.assertIn("spec_to_agent", registry)
        self.assertIn("acceptance_review", registry)

    def test_default_task_service_can_create_native_tasks(self):
        """
        验证 TaskService 能够正确解析并创建 Evoloop 3.0 原生任务。

        业务输入：
        - type: "spec_to_agent"
        - inputs: {"username": "alice", "business_intent": "编译登录需求"}

        断言：
        - 确认任务创建成功，且其定义类型为 "spec_to_agent"。
        """
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        service = build_default_task_service(root=Path(temp.name))

        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "编译登录需求",
            },
        )

        self.assertEqual(task.definition.type, "spec_to_agent")

    def test_default_task_service_registers_real_codex_handler(self):
        """默认 TaskService 应自动注册真实 codex handler，作为第一版 peer dispatch 基线。"""
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        service = build_default_task_service(root=Path(temp.name))

        self.assertIn("codex", service.peer_adapter.adapters)

    def test_create_task_api_accepts_spec_to_agent_business_intent(self):
        """
        验证 HTTP API 能够接收并正确解析 spec_to_agent 任务的创建负载。

        断言：
        - HTTP POST /api/tasks 返回 200。
        - 获取新创建的 Task 对象并确认其类型为 "spec_to_agent"。
        - 确认业务意图（business_intent）在上下文输入中完整保存。
        """
        service, _, _ = self.make_service()
        client = TestClient(create_app(service))

        response = client.post(
            "/api/tasks",
            json={
                "type": "spec_to_agent",
                "username": "alice",
                "business_intent": "编译登录需求",
            },
        )

        self.assertEqual(response.status_code, 200)
        task = service.get_task(response.json()["task_id"])
        self.assertEqual(task.definition.type, "spec_to_agent")
        self.assertEqual(task.context.inputs["business_intent"], "编译登录需求")

    def test_create_task_api_accepts_acceptance_review_payload(self):
        """
        验证 HTTP API 能够接收并正确解析 acceptance_review 任务的创建负载。

        断言：
        - HTTP POST /api/tasks 返回 200。
        - 获取新创建的 Task 对象并确认其类型为 "acceptance_review"。
        - 确认输入参数（machine_spec, acceptance_protocol, implementation_summary, diff）均正确留存。
        """
        service, _, _ = self.make_service()
        client = TestClient(create_app(service))

        response = client.post(
            "/api/tasks",
            json={
                "type": "acceptance_review",
                "username": "alice",
                "machine_spec": "req_login: 用户必须能登录",
                "acceptance_protocol": "case_login: 校验登录成功",
                "implementation_summary": "已完成登录接口与前端流程",
                "diff": "+ add login handler",
            },
        )

        self.assertEqual(response.status_code, 200)
        task = service.get_task(response.json()["task_id"])
        self.assertEqual(task.definition.type, "acceptance_review")
        self.assertEqual(task.context.inputs["machine_spec"], "req_login: 用户必须能登录")
        self.assertEqual(task.context.inputs["acceptance_protocol"], "case_login: 校验登录成功")
        self.assertEqual(task.context.inputs["implementation_summary"], "已完成登录接口与前端流程")
        self.assertEqual(task.context.inputs["diff"], "+ add login handler")

    def test_peer_result_api_records_delivery_bundle_and_runs_followup_review(self):
        """外部 AI 技术同事应能通过 API 回传 result bundle，并触发 follow-up review。"""
        service, storage, _ = self.make_service()
        client = TestClient(create_app(service))
        repair_task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "Repair auth branch",
                "parent_work_id": "task_review_parent",
                "iteration": 1,
                "review_cycle_id": "review_cycle_task_review_parent",
                "machine_spec": "req_login:",
                "acceptance_protocol": "Given unauthenticated request, Then return 401",
            },
        )

        response = client.post(
            f"/api/tasks/{repair_task.task_id}/peer-result",
            json={
                "peer_target": "codex",
                "implementation_summary": "Auth failure branch implemented by peer collaborator",
                "diff": "+ return 401 when token missing",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        refreshed_repair = storage.load_task(repair_task.task_id, service.registry)
        followup_review = storage.load_task(payload["followup_review_id"], service.registry)

        self.assertEqual(payload["status"], "completed")
        self.assertEqual(refreshed_repair.context.inputs["delivery_bundle"]["peer_target"], "codex")
        self.assertEqual(followup_review.definition.type, "acceptance_review")

    def test_peer_dispatch_api_runs_registered_handler_and_records_completion(self):
        """控制面应能通过 API 主动派发已注册的 PeerAdapter handler。"""
        service, storage, _ = self.make_service()
        client = TestClient(create_app(service))

        class CodexHandler:
            def execute(self, task, package_text):
                return {
                    "peer_target": "codex",
                    "implementation_summary": "Peer completed the implementation",
                    "diff": "+ add implementation",
                }

        service.peer_adapter.register_adapter("codex", CodexHandler())
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "Implement login flow",
            },
        )
        service.run_task(task.task_id)

        response = client.post(f"/api/tasks/{task.task_id}/peer-dispatch", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        refreshed_task = storage.load_task(task.task_id, service.registry)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["peer_target"], "codex")
        self.assertEqual(refreshed_task.context.inputs["delivery_bundle"]["peer_target"], "codex")

    def test_default_app_wiring_accepts_native_spec_to_agent_post(self):
        """
        验证当底层使用真实 Mock 环境打补丁（OpenAILLM, GBrainKnowledge）时，HTTP 创建 API 能否通畅运行。

        Mock 拦截：
        - patch "app.api.server.OpenAILLM" -> FakeDefaultLLM
        - patch "app.api.server.GBrainKnowledge" -> FakeDefaultKnowledge

        断言：
        - POST 创建请求返回 HTTP 200。
        - 响应 JSON 中包含 task_id，且状态为 "created"。
        """
        class FakeDefaultLLM(FakeLLM):
            def __init__(self, api_key="", base_url=""):
                self.api_key = api_key
                self.base_url = base_url

        class FakeDefaultKnowledge(FakeKnowledge):
            def __init__(self, repo_path, timeout_seconds=5):
                self.repo_path = repo_path
                self.timeout_seconds = timeout_seconds

        with patch("app.api.server.OpenAILLM", FakeDefaultLLM), patch("app.api.server.GBrainKnowledge", FakeDefaultKnowledge):
            client = TestClient(create_app())
            response = client.post(
                "/api/tasks",
                json={
                    "type": "spec_to_agent",
                    "username": "alice",
                    "business_intent": "编译登录需求",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("task_id", payload)
        self.assertEqual(payload["status"], "created")

    def test_product_context_and_mcp_context_serialize_native_requirements(self):
        """
        测试 ProductContext 与 MCP 工具获取接口是否能正确提取和序列化原生的业务需求陈述。

        断言：
        - 验证 TaskService.get_product_context() 返回的需求 statement。
        - 通过 Mock 方式调用 MCP 注册工具 "get_project_context"，验证输出的 JSON 中 requirements 声明与原输入一致。
        """
        service, _, _ = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "将登录需求编译成 agent 可执行任务包",
            },
        )
        context = service.get_product_context(task.task_id)
        self.assertEqual(context.requirements[0].statement, "将登录需求编译成 agent 可执行任务包")

        # 模拟 MCP 服务层，注册并调用其暴露出来的 Python 形式工具
        class DummyMCP:
            def __init__(self):
                self.funcs = {}

            def tool(self):
                def decorator(fn):
                    self.funcs[fn.__name__] = fn
                    return fn
                return decorator

        dummy = DummyMCP()
        register_tools(dummy)
        with patch("app.mcp.tools.get_service", return_value=service):
            payload = json.loads(dummy.funcs["get_project_context"](task.task_id))

        self.assertEqual(payload["requirements"][0]["statement"], "将登录需求编译成 agent 可执行任务包")

    def test_native_artifact_graph_uses_native_node_types(self):
        """
        测试在 spec_to_agent 工作流完整跑完后，生成的产物图节点类型是否正确映射到 3.0 的原生枚举。

        业务输入：
        - 执行 spec_to_agent 任务，拉取其生成的 ArtifactGraph。

        断言：
        - 检查 "machine_spec.yaml" 节点为 MACHINE_SPEC 类型。
        - 检查 "human_brief.md" 节点为 HUMAN_BRIEF 类型。
        - 检查 "agent_package_codex.md" 节点为 AGENT_PACKAGE 类型。
        - 检查 "acceptance.md" 节点为 ACCEPTANCE_PROTOCOL 类型。
        - 检查 "review_checklist.md" 节点为 REVIEW_CHECKLIST 类型。
        - 检查 "traceability.json" 节点为 TRACEABILITY_MAP 类型。
        """
        service, _, _ = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "将登录需求编译成 agent 可执行任务包",
            },
        )
        service.run_task(task.task_id)

        graph = service.get_artifact_graph(task.task_id)
        node_types_by_name = {node.artifact_ref.name: node.type for node in graph.nodes}

        self.assertEqual(node_types_by_name["machine_spec.yaml"], ArtifactNodeType.MACHINE_SPEC)
        self.assertEqual(node_types_by_name["human_brief.md"], ArtifactNodeType.HUMAN_BRIEF)
        self.assertEqual(node_types_by_name["agent_package_codex.md"], ArtifactNodeType.AGENT_PACKAGE)
        self.assertEqual(node_types_by_name["acceptance.md"], ArtifactNodeType.ACCEPTANCE_PROTOCOL)
        self.assertEqual(node_types_by_name["review_checklist.md"], ArtifactNodeType.REVIEW_CHECKLIST)
        self.assertEqual(node_types_by_name["traceability.json"], ArtifactNodeType.TRACEABILITY_MAP)

    def test_work_items_api_lists_native_work(self):
        """
        测试工作项 API (GET /api/work-items) 能否合理地输出 3.0 原生类型的任务。

        业务输入：
        - 创建 3.0 原生任务 (spec_to_agent)。
        - 创建 3.0 验收审查任务 (acceptance_review)。

        断言：
        - 确认 API 返回的列表中，各自的 work_type 映射正确。
        """
        service, _, _ = self.make_service()
        native_task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "将登录需求编译成 agent 可执行任务包",
            },
        )
        review_task = service.create_task(
            "acceptance_review",
            {
                "username": "alice",
                "machine_spec": "req_login: 用户必须能登录",
                "acceptance_protocol": "case_login: 校验登录成功",
                "implementation_summary": "已完成登录接口与前端流程",
                "diff": "+ add login handler",
            },
        )

        client = TestClient(create_app(service))
        response = client.get("/api/work-items")

        self.assertEqual(response.status_code, 200)
        work_items = {item["work_id"]: item for item in response.json()["work_items"]}
        self.assertEqual(work_items[native_task.task_id]["work_type"], "spec_to_agent")
        self.assertEqual(work_items[review_task.task_id]["work_type"], "acceptance_review")

    def test_work_item_detail_api_returns_frozen_contract_payload(self):
        """
        验证获取特定工作项详情 API (GET /api/work-items/{work_id}) 时，是否能返回冻结状态的契约信息。

        断言：
        - 确认返回的 work_id 与任务 ID 一致。
        - 确认 work_type 正确。
        - 确认 product_context_ref 返回相应的上下文 ID。
        """
        service, _, _ = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "将登录需求编译成 agent 可执行任务包",
            },
        )

        client = TestClient(create_app(service))
        response = client.get(f"/api/work-items/{task.task_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["work_id"], task.task_id)
        self.assertEqual(payload["work_type"], "spec_to_agent")
        self.assertEqual(payload["product_context_ref"], f"ctx_{task.task_id}")

    def test_work_item_product_context_api_returns_native_requirement(self):
        """
        验证获取工作项产品上下文 API (GET /api/work-items/{work_id}/product-context) 是否能返回原生需求声明。

        断言：
        - 确认 requirements 列表中第一项的陈述符合业务意图。
        """
        service, _, _ = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "将登录需求编译成 agent 可执行任务包",
            },
        )

        client = TestClient(create_app(service))
        response = client.get(f"/api/work-items/{task.task_id}/product-context")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["requirements"][0]["statement"], "将登录需求编译成 agent 可执行任务包")

    def test_work_item_artifact_graph_api_returns_native_node_types(self):
        """
        验证通过 API 接口获取的产物图 (GET /api/work-items/{work_id}/artifact-graph) 的节点类型命名是否符合 3.0 规范。

        断言：
        - 确认 machine_spec.yaml 对应的节点类型为 "machine_spec"。
        - 确认 agent_package_codex.md 对应的节点类型为 "agent_package"。
        """
        service, _, _ = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "将登录需求编译成 agent 可执行任务包",
            },
        )
        service.run_task(task.task_id)

        client = TestClient(create_app(service))
        response = client.get(f"/api/work-items/{task.task_id}/artifact-graph")

        self.assertEqual(response.status_code, 200)
        node_types_by_name = {
            node["artifact_ref"]["name"]: node["type"]
            for node in response.json()["nodes"]
        }
        self.assertEqual(node_types_by_name["machine_spec.yaml"], "machine_spec")
        self.assertEqual(node_types_by_name["agent_package_codex.md"], "agent_package")

    def test_workflow_step_status_flow_completes_spec_to_agent(self):
        """
        测试 spec_to_agent 编排执行时，其存储在 FakeStorage 里的事件流是否符合开始、完成和任务关闭的顺序。

        断言：
        - 任务执行状态为 COMPLETED。
        - 验证任务生成的事件流中包含 workflow.step.started, workflow.step.completed 以及 task.completed。
        """
        service, storage, _ = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "设计商品详情接口",
            },
        )

        result = service.run_task(task.task_id)

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        task_events = storage.read_events(task.task_id)
        event_types = [event.type for event in task_events]
        self.assertIn("workflow.step.started", event_types)
        self.assertIn("workflow.step.completed", event_types)
        self.assertIn("task.completed", event_types)

    def test_recent_conversations_returns_all_tasks_without_truncation(self):
        """
        测试最近对话接口 (GET /api/conversations/recent) 不进行人为截断，能如实拉取所有历史会话（本测试创建 25 个）。

        断言：
        - 检查今日、昨日、更早的会话总数相加，必须刚好为 25 个。
        """
        service, _, _ = self.make_service()
        for index in range(25):
            service.create_task(
                "spec_to_agent",
                {
                    "username": "alice",
                    "business_intent": f"验证最近对话列表不截断 {index}",
                },
            )

        client = TestClient(create_app(service))
        response = client.get('/api/conversations/recent')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        total = len(payload.get('today', [])) + len(payload.get('yesterday', [])) + len(payload.get('older', []))
        self.assertEqual(total, 25)

    def test_workflow_run_and_step_events_include_timing_metadata(self):
        """
        测试工作流执行事件中是否均附加了执行计时信息（duration_ms）。

        断言：
        - 检查 workflow.run.started 事件是否产生了正确的 run_id (以 run_ 开头)。
        - 检查 workflow.run.completed 和 workflow.step.completed 事件是否携带了非负的整数 duration_ms。
        - 确认该次运行内所有步骤事件均共享同一个 run_id。
        """
        service, storage, _ = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "性能诊断",
            },
        )

        service.run_task(task.task_id)

        events = [event.to_dict() for event in storage.read_events(task.task_id)]
        # 提取各个关键生命周期节点的时间监控数据
        run_started = [event for event in events if event["type"] == "workflow.run.started"]
        run_completed = [event for event in events if event["type"] == "workflow.run.completed"]
        step_completed = [event for event in events if event["type"] == "workflow.step.completed"]

        self.assertEqual(len(run_started), 1)
        self.assertEqual(len(run_completed), 1)
        run_id = run_started[0]["payload"].get("run_id")
        self.assertTrue(run_id.startswith("run_"))
        self.assertEqual(run_completed[0]["payload"].get("run_id"), run_id)
        self.assertIsInstance(run_completed[0]["payload"].get("duration_ms"), int)
        self.assertGreaterEqual(run_completed[0]["payload"].get("duration_ms"), 0)
        self.assertTrue(step_completed)
        self.assertTrue(all(event["payload"].get("run_id") == run_id for event in step_completed))
        self.assertTrue(all(isinstance(event["payload"].get("duration_ms"), int) for event in step_completed))

    def test_llm_telemetry_events_are_recorded_without_sensitive_payloads(self):
        """
        测试 LLM 调用的遥测数据收集是否能够在记录监控时剔除 prompt、api_key 等敏感信息。

        模拟：
        - TelemetryLLM 自定义实现了流式调用并主动触发了 llm.call.started / llm.call.completed 等监控。
        - 其入参包括 secret-key 和 prompt。

        断言：
        - 验证各个 llm.call.xxx 事件均已捕获。
        - 验证事件负载中不包含 "prompt" 或 "api_key"。
        - 验证包含当前的执行步骤 ID (step_id) 和运行 ID (run_id)。
        """
        class TelemetryLLM:
            def invoke_stream(self, role, prompt, context, telemetry=None):
                if telemetry:
                    # 触发模拟遥测开始
                    telemetry(
                        "llm.call.started",
                        {
                            "call_id": "llm_test_call",
                            "model": "diagnostic-model",
                            "base_url_host": "relay.example.test",
                            "prompt": "must not be stored",
                            "api_key": "secret-key",
                        },
                    )
                    telemetry("llm.call.headers_received", {"call_id": "llm_test_call", "ttfb_ms": 12})
                    telemetry("llm.call.first_token", {"call_id": "llm_test_call", "first_token_ms": 34})
                yield "hello"
                yield " world"
                if telemetry:
                    # 触发模拟遥测完成
                    telemetry(
                        "llm.call.completed",
                        {
                            "call_id": "llm_test_call",
                            "duration_ms": 56,
                            "output_chars": 11,
                            "chunk_count": 2,
                        },
                    )

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        registry = build_task_registry()
        storage = FakeStorage(root)
        tool_service = ToolService.default(root=root, knowledge=FakeKnowledge())
        engine = WorkflowEngine(tool_service=tool_service, llm=TelemetryLLM(), storage=storage)
        service = TaskService(registry=registry, engine=engine, storage=storage)
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "判断慢是否来自模型链路",
            },
        )

        service.run_task(task.task_id, until_step_id="open_question_identifier")

        events = [event.to_dict() for event in storage.read_events(task.task_id)]
        llm_events = [event for event in events if event["type"].startswith("llm.call.")]
        event_types = [event["type"] for event in llm_events]
        self.assertIn("llm.call.started", event_types)
        self.assertIn("llm.call.headers_received", event_types)
        self.assertIn("llm.call.first_token", event_types)
        self.assertIn("llm.call.completed", event_types)
        # 审计遥测负载是否泄露隐私
        for event in llm_events:
            payload = event["payload"]
            self.assertEqual(payload.get("step_id"), "open_question_identifier")
            self.assertTrue(payload.get("run_id", "").startswith("run_"))
            self.assertNotIn("prompt", payload)
            self.assertNotIn("api_key", payload)

    def test_needs_arbitration_pauses_and_resumes(self):
        """
        测试当工作流遇到需要决策仲裁的步骤时，是否能进入 WAITING_FOR_USER 挂起状态并成功恢复。

        业务输入：
        - 注入会返回歧义提问的 ArbitrationLLM，以在 human_decision_gate 触发仲裁。

        断言与恢复：
        - 验证初次运行返回状态为 WAITING_FOR_USER。
        - 调用 service.apply_decision() 注入用户决策并恢复执行。
        - 验证任务最终流转到 COMPLETED 状态。
        - 验证存储的上下文与事件中正确持久化了用户的具体选择（selected_option）。
        """
        class ArbitrationLLM(FakeLLM):
            def invoke(self, role, prompt, context):
                if role == "Compiler" and ("missing Domain-Driven Design" in prompt or "OpenQuestionIdentifier" in prompt):
                    return LLMResult(
                        content='{"has_questions": true, "questions": ["Is consistency required?"]}',
                        structured={"has_questions": True, "questions": ["Is consistency required?"]}
                    )
                return super().invoke(role, prompt, context)

        service, storage, _ = self.make_service()
        service.engine.llm = ArbitrationLLM()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "结算重试策略",
            },
        )

        # 首次执行至仲裁门控挂起
        paused = service.run_task(task.task_id)
        self.assertEqual(paused.status, TaskStatus.WAITING_FOR_USER)
        self.assertEqual(paused.waiting_step_id, "human_decision_gate")

        # 载入用户决策以恢复
        resumed = service.apply_decision(
            task.task_id,
            decision="选择方案 B，接受短时间缓存脏数据，但必须加入事后对账。",
            selected_option="B",
        )

        self.assertEqual(resumed.status, TaskStatus.COMPLETED)
        context = storage.load_context(task.task_id)
        self.assertEqual(context.user_decisions[0].selected_option, "B")
        event_types = [event.type for event in storage.read_events(task.task_id)]
        self.assertIn("arbitration.requested", event_types)
        self.assertIn("arbitration.applied", event_types)

    def test_apply_decision_persists_quoted_selections(self):
        """
        验证用户进行仲裁恢复时所选定的引用内容（quoted_selections）能够正确被序列化并包含在 applied 事件中。

        断言：
        - 挂起并注入带 quoted_selections 的决策。
        - 恢复后确认 context 和 arbitration.applied 事件中均包含了该引用块数据。
        """
        class ArbitrationLLM(FakeLLM):
            def invoke(self, role, prompt, context):
                if role == "Compiler" and ("missing Domain-Driven Design" in prompt or "OpenQuestionIdentifier" in prompt):
                    return LLMResult(
                        content='{"has_questions": true, "questions": ["Is consistency required?"]}',
                        structured={"has_questions": True, "questions": ["Is consistency required?"]}
                    )
                return super().invoke(role, prompt, context)

        service, storage, _ = self.make_service()
        service.engine.llm = ArbitrationLLM()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "引用片段决策",
            },
        )

        paused = service.run_task(task.task_id)
        self.assertEqual(paused.status, TaskStatus.WAITING_FOR_USER)

        quoted_selections = [
            {
                "source_type": "message",
                "source_id": "msg_1",
                "source_label": "Compiler Agent",
                "text": "需要保留这个引用来源",
            }
        ]
        resumed = service.apply_decision(
            task.task_id,
            decision="按引用内容继续修改",
            selected_option="A",
            quoted_selections=quoted_selections,
        )

        self.assertEqual(resumed.status, TaskStatus.COMPLETED)
        context = storage.load_context(task.task_id)
        self.assertEqual(context.user_decisions[0].quoted_selections, quoted_selections)
        applied_events = [event.to_dict() for event in storage.read_events(task.task_id) if event.type == "arbitration.applied"]
        self.assertEqual(applied_events[0]["payload"]["quoted_selections"], quoted_selections)

    def test_checkpoint_restore_continues_from_last_successful_step(self):
        """
        验证检查点恢复机制。

        验证当任务在前置步骤（如 context_normalizer）运行完且将检查点存盘后，
        即使重新创建一个全新的 TaskService 和引擎实例，也能无缝从该检查点继续向后执行直到完成。
        """
        service, storage, _ = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "灰度发布",
            },
        )
        # 部分执行并存盘
        service.run_task(task.task_id, until_step_id="context_normalizer")
        checkpoint = storage.load_checkpoint(task.task_id)
        self.assertEqual(checkpoint["last_completed_step_id"], "context_normalizer")

        # 实例化全新的引擎和服务以恢复状态
        registry = build_task_registry()
        restored_engine = WorkflowEngine(
            tool_service=ToolService.default(root=storage.root, knowledge=FakeKnowledge()),
            llm=FakeLLM(),
            storage=storage,
        )
        restored = TaskService(registry=registry, engine=restored_engine, storage=storage)
        result = restored.run_task(task.task_id)

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        latest = storage.load_checkpoint(task.task_id)
        self.assertEqual(latest["last_completed_step_id"], "final_checkpoint")

    def test_tool_policy_allows_and_denies(self):
        """
        验证工具策略权限白名单校验。

        业务规则：
        - 验证在白名单内的工具调用（如 retrieve_knowledge，对于 SYSTEM 角色）能返回 succeeded。
        - 验证不在白名单或角色无权调用的工具（如对于 Compiler 角色的 artifact.write）被正确拦截并返回 denied 状态，携带 tool.denied 错误码。
        """
        service, _, tool_service = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "统一鉴权",
            },
        )
        # 发起授权调用
        allowed = tool_service.invoke(
            task.definition,
            task.context,
            ToolCall(
                task_id=task.task_id,
                step_id="open_question_identifier",
                agent_role="SYSTEM",
                tool_name="knowledge.retrieve",
                arguments={"query": "鉴权"},
            ),
        )
        # 发起越权调用
        denied = tool_service.invoke(
            task.definition,
            task.context,
            ToolCall(
                task_id=task.task_id,
                step_id="open_question_identifier",
                agent_role="Compiler",
                tool_name="artifact.write",
                arguments={"name": "machine_spec.yaml", "content": "# bad"},
            ),
        )

        self.assertEqual(allowed.status, "succeeded")
        self.assertEqual(denied.status, "denied")
        self.assertEqual(denied.error.code, "tool.denied")

    def test_fork_repair_work_item_creates_bounded_iteration_task(self):
        """Acceptance Review 未通过时应能 fork 有界修复 WorkItem，而不是静默结束。"""
        service, storage, _ = self.make_service()
        review_task = service.create_task(
            "acceptance_review",
            {
                "username": "alice",
                "machine_spec": "req_login:",
                "acceptance_protocol": "Given unauthenticated request, Then return 401",
                "implementation_summary": "TODO auth branch",
                "diff": "+ // TODO: auth branch",
                "machine_spec_ref": "memory://machine_spec",
                "acceptance_protocol_ref": "memory://acceptance",
                "max_review_iterations": 2,
            },
        )
        review_task.context.inputs["iteration"] = 0
        storage.save_context(review_task.context)
        review_result = {
            "verdict": "changes_required",
            "fix_tasks": [
                {
                    "task_id": "fix_0",
                    "priority": "high",
                    "title": "Implement auth failure branch",
                    "source_issue_ids": ["issue_0"],
                }
            ],
        }

        repair_task = service.fork_repair_work_item(review_task.task_id, review_result)
        repair_context = storage.load_context(repair_task.task_id)
        repair_work_item = service.get_work_item(repair_task.task_id)
        event_types = [event.type for event in storage.read_events(review_task.task_id)]

        self.assertEqual(repair_task.definition.type, "spec_to_agent")
        self.assertEqual(repair_context.inputs["parent_work_id"], review_task.task_id)
        self.assertEqual(repair_context.inputs["iteration"], 1)
        self.assertEqual(repair_context.inputs["review_cycle_id"], f"review_cycle_{review_task.task_id}")
        self.assertEqual(repair_context.inputs["fix_tasks"][0]["title"], "Implement auth failure branch")
        self.assertEqual(repair_work_item.parent_work_id, review_task.task_id)
        self.assertEqual(repair_work_item.iteration, 1)
        self.assertIn("review.redo.forked", event_types)

    def test_handle_review_result_forks_repair_for_changes_required(self):
        """Review verdict=changes_required 时控制面应自动 fork 下一轮修复任务。"""
        service, storage, _ = self.make_service()
        review_task = service.create_task(
            "acceptance_review",
            {
                "username": "alice",
                "machine_spec": "req_login:",
                "acceptance_protocol": "Given unauthenticated request, Then return 401",
                "implementation_summary": "TODO auth branch",
                "diff": "+ // TODO: auth branch",
                "max_review_iterations": 2,
            },
        )
        review_task.context.step_outputs["review_result_compiler"] = {
            "review_result": {
                "verdict": "changes_required",
                "fix_tasks": [
                    {
                        "task_id": "fix_0",
                        "priority": "high",
                        "title": "Implement auth failure branch",
                        "source_issue_ids": ["issue_0"],
                    }
                ],
            }
        }
        storage.save_context(review_task.context)

        repair_task = service.handle_review_result(review_task.task_id)
        refreshed_review = storage.load_task(review_task.task_id, service.registry)
        event_types = [event.type for event in storage.read_events(review_task.task_id)]

        self.assertIsNotNone(repair_task)
        self.assertEqual(repair_task.definition.type, "spec_to_agent")
        self.assertEqual(refreshed_review.context.inputs["latest_repair_work_id"], repair_task.task_id)
        self.assertIn("review.redo.forked", event_types)

    def test_create_followup_acceptance_review_from_repair_task(self):
        """修复任务完成后，控制面应能自动创建下一轮 acceptance_review。"""
        service, storage, _ = self.make_service()
        repair_task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "Repair auth branch",
                "parent_work_id": "task_review_parent",
                "iteration": 1,
                "review_cycle_id": "review_cycle_task_review_parent",
                "machine_spec": "req_login:",
                "acceptance_protocol": "Given unauthenticated request, Then return 401",
                "delivery_bundle": {
                    "implementation_summary": "Auth failure branch implemented",
                    "diff": "+ return 401 when token missing",
                },
            },
        )

        followup_review = service.create_followup_acceptance_review(repair_task.task_id)
        followup_context = storage.load_context(followup_review.task_id)
        followup_work_item = service.get_work_item(followup_review.task_id)
        event_types = [event.type for event in storage.read_events(repair_task.task_id)]

        self.assertEqual(followup_review.definition.type, "acceptance_review")
        self.assertEqual(followup_context.inputs["machine_spec"], "req_login:")
        self.assertEqual(followup_context.inputs["acceptance_protocol"], "Given unauthenticated request, Then return 401")
        self.assertEqual(followup_context.inputs["implementation_summary"], "Auth failure branch implemented")
        self.assertEqual(followup_context.inputs["diff"], "+ return 401 when token missing")
        self.assertEqual(followup_context.inputs["parent_work_id"], repair_task.task_id)
        self.assertEqual(followup_context.inputs["iteration"], 1)
        self.assertEqual(followup_context.inputs["review_cycle_id"], "review_cycle_task_review_parent")
        self.assertEqual(followup_work_item.parent_work_id, repair_task.task_id)
        self.assertEqual(followup_work_item.iteration, 1)
        self.assertIn("review.followup.created", event_types)

    def test_handle_repair_completion_runs_followup_acceptance_review(self):
        """修复任务完成后，控制面应自动运行下一轮复审并产出 review_result.md。"""
        service, storage, _ = self.make_service()
        repair_task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "Repair auth branch",
                "parent_work_id": "task_review_parent",
                "iteration": 1,
                "review_cycle_id": "review_cycle_task_review_parent",
                "machine_spec": "req_login:",
                "acceptance_protocol": "Given unauthenticated request, Then return 401",
                "delivery_bundle": {
                    "implementation_summary": "Auth failure branch implemented",
                    "diff": "+ return 401 when token missing",
                },
            },
        )
        repair_task.status = TaskStatus.COMPLETED
        storage.save_task(repair_task)

        followup_review = service.handle_repair_completion(repair_task.task_id)
        refreshed_repair = storage.load_task(repair_task.task_id, service.registry)
        followup_artifact_names = [artifact.name for artifact in storage.list_artifacts(followup_review.task_id)]
        event_types = [event.type for event in storage.read_events(repair_task.task_id)]

        self.assertEqual(followup_review.definition.type, "acceptance_review")
        self.assertEqual(followup_review.status, TaskStatus.COMPLETED)
        self.assertEqual(refreshed_repair.context.inputs["latest_followup_review_id"], followup_review.task_id)
        self.assertIn("review_result.md", followup_artifact_names)
        self.assertIn("review.followup.created", event_types)
        self.assertIn("review.followup.run.completed", event_types)

    def test_handle_repair_completion_reenters_bounded_redo_when_followup_review_fails(self):
        """follow-up review 再次未通过时，控制面应继续有界 fork 下一轮 repair。"""
        service, storage, _ = self.make_service()
        repair_task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "Repair auth branch",
                "parent_work_id": "task_review_parent",
                "iteration": 1,
                "review_cycle_id": "review_cycle_task_review_parent",
                "max_review_iterations": 3,
                "machine_spec": "req_login:",
                "acceptance_protocol": "Given unauthenticated request, Then return 401",
                "delivery_bundle": {
                    "implementation_summary": "Auth branch still incomplete",
                    "diff": "+ // TODO: token missing path still not handled",
                },
            },
        )
        repair_task.status = TaskStatus.COMPLETED
        storage.save_task(repair_task)

        followup_review = service.handle_repair_completion(repair_task.task_id)
        refreshed_review = storage.load_task(followup_review.task_id, service.registry)
        next_repair_task_id = refreshed_review.context.inputs.get("latest_repair_work_id")
        next_repair_task = storage.load_task(next_repair_task_id, service.registry)
        review_event_types = [event.type for event in storage.read_events(followup_review.task_id)]

        self.assertEqual(followup_review.status, TaskStatus.COMPLETED)
        self.assertIsNotNone(next_repair_task_id)
        self.assertEqual(next_repair_task.definition.type, "spec_to_agent")
        self.assertEqual(next_repair_task.context.inputs["iteration"], 2)
        self.assertEqual(next_repair_task.context.inputs["parent_work_id"], followup_review.task_id)
        self.assertIn("review.redo.forked", review_event_types)

    def test_complete_peer_collaboration_persists_delivery_bundle_and_triggers_followup_review(self):
        """PeerAdapter 返回真实 result bundle 后，控制面应写入 delivery_bundle 并自动进入 follow-up review。"""
        service, storage, _ = self.make_service()
        repair_task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "Repair auth branch",
                "parent_work_id": "task_review_parent",
                "iteration": 1,
                "review_cycle_id": "review_cycle_task_review_parent",
                "machine_spec": "req_login:",
                "acceptance_protocol": "Given unauthenticated request, Then return 401",
            },
        )

        peer_result = {
            "peer_target": "codex",
            "implementation_summary": "Auth failure branch implemented by peer collaborator",
            "diff": "+ return 401 when token missing",
            "artifacts": [{"path": "src/auth.py", "kind": "code"}],
        }

        followup_review = service.complete_peer_collaboration(repair_task.task_id, peer_result)
        refreshed_repair = storage.load_task(repair_task.task_id, service.registry)
        event_types = [event.type for event in storage.read_events(repair_task.task_id)]

        self.assertEqual(refreshed_repair.status, TaskStatus.COMPLETED)
        self.assertEqual(
            refreshed_repair.context.inputs["delivery_bundle"]["implementation_summary"],
            "Auth failure branch implemented by peer collaborator",
        )
        self.assertEqual(
            refreshed_repair.context.inputs["delivery_bundle"]["diff"],
            "+ return 401 when token missing",
        )
        self.assertEqual(refreshed_repair.context.inputs["delivery_bundle"]["peer_target"], "codex")
        self.assertEqual(followup_review.definition.type, "acceptance_review")
        self.assertIn("peer.delivery_bundle.recorded", event_types)
        self.assertIn("peer.collaboration.completed", event_types)
        self.assertIn("review.followup.run.completed", event_types)

    def test_spawn_formal_subtask_persists_child_metadata(self):
        """formal_subtask 应复用普通 Task/WorkItem 并保留父子元数据。"""
        from app.core.subagent import SubagentBudget, SubagentScope, SubagentSpawnRequest

        service, storage, _ = self.make_service()
        parent = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "Repair checkout rules",
                "machine_spec": "req_coupon:",
                "acceptance_protocol": "Given coupon, Then rules apply",
                "review_cycle_id": "review_cycle_task_parent",
                "max_review_iterations": 2,
            },
        )
        request = SubagentSpawnRequest(
            scope=SubagentScope.FORMAL_SUBTASK,
            goal="Repair coupon stacking rule",
            task_slice="Only repair checkout stacking rule",
            input_refs=["fix_task"],
            input_excerpt={
                "username": "alice",
                "business_intent": "Repair coupon stacking rule",
                "machine_spec": "req_coupon:",
                "acceptance_protocol": "Given coupon, Then rules apply",
                "fix_tasks": [{"title": "Repair coupon stacking rule", "source_issue_ids": ["issue_coupon"]}],
            },
            allowed_tools=[],
            output_schema={"implementation_summary": "string"},
            budget=SubagentBudget(max_iterations=3, max_input_tokens=400, max_output_tokens=200, max_tool_calls=2, spawn_fanout_remaining=0),
            task_type="spec_to_agent",
            subtask_type="repair_coupon_rule",
            join_step_id="review.followup",
            acceptance_slice={"requirement_ids": ["req_coupon"]},
            subtask_index=0,
        )

        child = service.spawn_formal_subtask(parent.task_id, request)
        child_context = storage.load_context(child.task_id)
        child_work_item = service.get_work_item(child.task_id)

        self.assertEqual(child_context.inputs["subagent_scope"], "formal_subtask")
        self.assertEqual(child_context.inputs["parent_task_id"], parent.task_id)
        self.assertEqual(child_context.inputs["subtask_type"], "repair_coupon_rule")
        self.assertEqual(child_work_item.parent_work_id, parent.task_id)
        self.assertEqual(child_work_item.metadata["subagent_scope"], "formal_subtask")

    def test_handle_review_result_fans_out_independent_fix_tasks_into_formal_subtasks(self):
        """独立 fix_tasks 应派生 coordinator repair task 与 formal subtasks。"""
        service, storage, _ = self.make_service()
        review_task = service.create_task(
            "acceptance_review",
            {
                "username": "alice",
                "machine_spec": "req_login:\nreq_trace:",
                "acceptance_protocol": "Given unauthenticated request, Then return 401",
                "implementation_summary": "TODO auth branch and docs",
                "diff": "+ // TODO",
                "max_review_iterations": 2,
            },
        )
        review_task.context.step_outputs["review_result_compiler"] = {
            "review_result": {
                "verdict": "changes_required",
                "fix_tasks": [
                    {
                        "task_id": "fix_0",
                        "priority": "high",
                        "title": "Implement auth failure branch",
                        "source_issue_ids": ["issue_auth"],
                    },
                    {
                        "task_id": "fix_1",
                        "priority": "medium",
                        "title": "Repair traceability docs",
                        "source_issue_ids": ["issue_trace"],
                    },
                ],
            }
        }
        storage.save_context(review_task.context)

        coordinator = service.handle_review_result(review_task.task_id)
        refreshed = storage.load_task(review_task.task_id, service.registry)
        child_ids = refreshed.context.inputs["latest_repair_work_ids"]
        child_tasks = [storage.load_task(task_id, service.registry) for task_id in child_ids]

        self.assertEqual(coordinator.definition.type, "spec_to_agent")
        self.assertEqual(len(child_ids), 2)
        self.assertTrue(all(task.context.inputs["subagent_scope"] == "formal_subtask" for task in child_tasks))

    def test_join_formal_subtasks_aggregates_delivery_bundle_and_triggers_followup(self):
        """所有 formal_subtask 完成后，应 join 为一个 delivery bundle 并进入 follow-up review。"""
        from app.core.subagent import SubagentBudget, SubagentScope, SubagentSpawnRequest

        service, storage, _ = self.make_service()
        coordinator = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "Repair checkout rules",
                "machine_spec": "req_coupon:\nreq_trace:",
                "acceptance_protocol": "Given coupon, Then rules apply",
                "review_cycle_id": "review_cycle_task_parent",
                "max_review_iterations": 2,
            },
        )
        requests = [
            SubagentSpawnRequest(
                scope=SubagentScope.FORMAL_SUBTASK,
                goal="Repair coupon stacking rule",
                task_slice="Only repair checkout stacking rule",
                input_refs=["fix_task"],
                input_excerpt={
                    "username": "alice",
                    "business_intent": "Repair coupon stacking rule",
                    "machine_spec": "req_coupon:\nreq_trace:",
                    "acceptance_protocol": "Given coupon, Then rules apply",
                    "fix_tasks": [{"title": "Repair coupon stacking rule", "source_issue_ids": ["issue_coupon"]}],
                },
                allowed_tools=[],
                output_schema={"implementation_summary": "string"},
                budget=SubagentBudget(max_iterations=3, max_input_tokens=400, max_output_tokens=200, max_tool_calls=2, spawn_fanout_remaining=0),
                task_type="spec_to_agent",
                subtask_type="repair_coupon_rule",
                join_step_id="review.followup",
                acceptance_slice={"requirement_ids": ["req_coupon"]},
                subtask_index=0,
            ),
            SubagentSpawnRequest(
                scope=SubagentScope.FORMAL_SUBTASK,
                goal="Repair traceability docs",
                task_slice="Only repair traceability docs",
                input_refs=["fix_task"],
                input_excerpt={
                    "username": "alice",
                    "business_intent": "Repair traceability docs",
                    "machine_spec": "req_coupon:\nreq_trace:",
                    "acceptance_protocol": "Given coupon, Then rules apply",
                    "fix_tasks": [{"title": "Repair traceability docs", "source_issue_ids": ["issue_trace"]}],
                },
                allowed_tools=[],
                output_schema={"implementation_summary": "string"},
                budget=SubagentBudget(max_iterations=3, max_input_tokens=400, max_output_tokens=200, max_tool_calls=2, spawn_fanout_remaining=0),
                task_type="spec_to_agent",
                subtask_type="repair_traceability",
                join_step_id="review.followup",
                acceptance_slice={"requirement_ids": ["req_trace"]},
                subtask_index=1,
            ),
        ]

        children = [service.spawn_formal_subtask(coordinator.task_id, request) for request in requests]
        for index, child in enumerate(children):
            service.complete_peer_collaboration(
                child.task_id,
                {
                    "peer_target": "codex",
                    "implementation_summary": f"Completed child {index}",
                    "diff": f"+ child {index} fix",
                    "artifacts": [{"path": f"src/child_{index}.py", "kind": "code"}],
                },
            )

        refreshed_parent = storage.load_task(coordinator.task_id, service.registry)
        event_types = [event.type for event in storage.read_events(coordinator.task_id)]
        followup_review_id = refreshed_parent.context.inputs["latest_followup_review_id"]
        followup_review = storage.load_task(followup_review_id, service.registry)

        self.assertEqual(refreshed_parent.status, TaskStatus.COMPLETED)
        self.assertIn("Completed child 0", refreshed_parent.context.inputs["delivery_bundle"]["implementation_summary"])
        self.assertIn("Completed child 1", refreshed_parent.context.inputs["delivery_bundle"]["implementation_summary"])
        self.assertEqual(followup_review.definition.type, "acceptance_review")
        self.assertIn("subagent.run.completed", event_types)
        self.assertIn("subagent.join.completed", event_types)
        self.assertIn("review.followup.run.completed", event_types)

    def test_start_peer_collaboration_dispatches_registered_handler_and_records_result(self):
        """已注册 PeerAdapter handler 时，控制面应真实派发 agent package 并回收 result bundle。"""
        service, storage, _ = self.make_service()

        class CodexHandler:
            def execute(self, task, package_text):
                self.task_id = task.task_id
                self.package_text = package_text
                return {
                    "peer_target": "codex",
                    "implementation_summary": "Peer completed the implementation",
                    "diff": "+ add implementation",
                }

        handler = CodexHandler()
        service.peer_adapter.register_adapter("codex", handler)
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "Implement login flow",
            },
        )
        service.run_task(task.task_id)

        completed_task = service.start_peer_collaboration(task.task_id)
        refreshed_task = storage.load_task(task.task_id, service.registry)
        event_types = [event.type for event in storage.read_events(task.task_id)]

        self.assertEqual(handler.task_id, task.task_id)
        self.assertIn("# Agent Package For AI Technical Peer", handler.package_text)
        self.assertEqual(completed_task.status, TaskStatus.COMPLETED)
        self.assertEqual(refreshed_task.context.inputs["delivery_bundle"]["peer_target"], "codex")
        self.assertIn("peer.collaboration.dispatch.started", event_types)
        self.assertIn("peer.collaboration.completed", event_types)

    def test_start_peer_collaboration_rejects_unregistered_handler_without_fake_success(self):
        """未注册 PeerAdapter handler 时，控制面应明确拒绝派发，而不是伪装成功。"""
        service, storage, _ = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "Implement login flow",
            },
        )
        service.run_task(task.task_id)

        with self.assertRaises(ValueError):
            service.start_peer_collaboration(task.task_id)

        refreshed_task = storage.load_task(task.task_id, service.registry)
        event_types = [event.type for event in storage.read_events(task.task_id)]
        self.assertNotIn("delivery_bundle", refreshed_task.context.inputs)
        self.assertIn("peer.collaboration.dispatch.failed", event_types)

    def test_artifact_write_is_idempotent_by_logical_name(self):
        """
        验证 artifact.write 写入操作的逻辑幂等性。

        即针对相同文件名连续调用写入时：
        - 状态均为 succeeded。
        - 生成的产物 ID 和版本应该一致。
        - 在物理存储层面，文件不应该发生冗余拷贝，总数量依然为 1。
        """
        service, storage, tool_service = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "生成账单 PRD",
            },
        )
        call = ToolCall(
            task_id=task.task_id,
            step_id="writer_machine_spec",
            agent_role="Writer",
            tool_name="artifact.write",
            arguments={"name": "machine_spec.yaml", "content": "# 账单中心\n"},
        )

        # 连续发起两次完全相同的写入调用
        first = tool_service.invoke(task.definition, task.context, call)
        second = tool_service.invoke(task.definition, task.context, call)

        self.assertEqual(first.status, "succeeded")
        self.assertEqual(second.status, "succeeded")
        self.assertEqual(first.artifacts[0].artifact_id, second.artifacts[0].artifact_id)
        self.assertEqual(first.artifacts[0].version, second.artifacts[0].version)
        self.assertEqual(len(storage.list_artifacts(task.task_id)), 1)

    def test_fake_llm_and_fake_tools_run_minimal_spec_to_agent_workflow(self):
        """
        使用 Fake 依赖运行最小可执行的 spec_to_agent 工作流并验证产出。

        业务输入：
        - business_intent: "提高客服响应效率"

        断言：
        - 验证任务最终运行为 COMPLETED。
        - 确认存储中写出了 "machine_spec.yaml"。
        - 检查内容包含 "提高客服响应效率" 等关键业务词。
        """
        service, storage, _ = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "bob",
                "business_intent": "提高客服响应效率",
            },
        )

        result = service.run_task(task.task_id)

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        artifacts = storage.list_artifacts(task.task_id)
        artifact_names = [artifact.name for artifact in artifacts]
        self.assertIn("machine_spec.yaml", artifact_names)
        spec = next(art for art in artifacts if art.name == "machine_spec.yaml")
        spec_content = storage.read_artifact(spec.artifact_id).content
        self.assertIn("提高客服响应效率", spec_content)

    def test_frontend_task_payload_exposes_knowledge_status(self):
        """
        验证前端获取的任务详情负载中正确暴露了底层知识检索的健康状态和结果条数。
        """
        service, storage, _ = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "让前端能看到知识检索状态",
            },
        )
        context = storage.load_context(task.task_id)
        # 伪造知识检索正常完成的场景
        context.degradation_state["knowledge"] = {"degraded": False, "items": 5, "preview": []}
        storage.save_context(context)
        task = storage.load_task(task.task_id, service.registry)

        self.assertIn("knowledge", task.context.degradation_state)
        self.assertEqual(task.context.degradation_state["knowledge"]["items"], 5)

    def test_frontend_task_status_maps_knowledge_state(self):
        """
        验证当前端通过 API 读取前端封装的任务视图时，能够将知识检索的具体状态合理映射。
        """
        from app.api.server import _frontend_task

        service, storage, _ = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "让前端能区分错误和无结果",
            },
        )
        context = storage.load_context(task.task_id)
        # 伪造知识检索正常完成但无结果的场景
        context.degradation_state["knowledge"] = {"degraded": False, "items": 0, "preview": []}
        storage.save_context(context)
        task = storage.load_task(task.task_id, service.registry)

        payload = _frontend_task(task)

        self.assertEqual(payload["knowledge_status"]["state"], "no_results")


if __name__ == "__main__":
    unittest.main()
