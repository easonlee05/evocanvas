"""FastAPI 接口服务模块，负责暴露 EvoCanvas 工作台与可复用底座能力。"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

# 优雅降级：支持在无 Web 运行期依赖的环境中进行单元测试和静态检查
try:
    from fastapi import FastAPI, File, HTTPException, UploadFile, BackgroundTasks, Body, Depends, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, StreamingResponse
    from app.api.auth import get_tenant_workspace
except Exception:  # pragma: no cover - 允许在无 fastapi 等 Web 依赖时安全导入
    FastAPI = None  # type: ignore
    File = None  # type: ignore
    HTTPException = Exception  # type: ignore
    UploadFile = object  # type: ignore
    BackgroundTasks = object  # type: ignore
    CORSMiddleware = None  # type: ignore
    Depends = object # type: ignore
    Request = object # type: ignore
    JSONResponse = None  # type: ignore
    StreamingResponse = None  # type: ignore
    class DummyBody:
        def __call__(self, *args, **kwargs):
            return None
    Body = DummyBody()

from app.api.canvas_schemas import (
    CanvasCardCreateRequest,
    CanvasCardMoveRequest,
    CanvasCardPatchRequest,
    CanvasMessageRequest,
    CanvasRelationCreateRequest,
    CanvasSnapshotCreateRequest,
)
from app.api.schemas import (
    CreateTaskRequest,
    DecisionRequest,
    KnowledgeCandidateCreateRequest,
    MaterialUploadResponse,
    SourceRefCreateRequest,
)
from app.canvas.service import (
    CanvasCardConfirmationRequiredError,
    CanvasCardNotFoundError,
    CanvasMessageValidationError,
    CanvasRelationNotFoundError,
    CanvasRelationValidationError,
    CanvasService,
    CanvasSnapshotNotFoundError,
    CanvasTurnInProgressError,
)
from app.canvas.agent_execution import PiRuntimeClient, PiRuntimeError, PiRuntimeUnknownError
from app.canvas.tool_gateway import RunScopedTokenCodec, ToolGateway, ToolGatewayError
from app.canvas.repository import PackageVersionStaleError
from app.services.fakes import FakeLLM, FakeStorage
from app.services.codex_cli_handler import CodexCLIHandler
from app.services.gbrain_service import GBrainKnowledge
from app.services.legacy_runtime import LazyLegacyWorkflowEngine
from app.services.peer_adapter_service import PeerAdapterService
from app.services.task_service import TaskService
from app.services.tool_service import ToolService
from app.workflows.definitions import build_task_registry
from app.core.events import EventBus

# 全局事件总线，用于实时推送工作流中的 Event 消息
global_event_bus = EventBus()
global_materials_cache = {}
global_knowledge_candidates_cache = {}
global_source_refs_cache = {}


# 智能 Agent 角色的前端展示元数据，包括名称、状态标签、头像缩写与配色设计
AGENT_META = {
    "Compiler": {"agent": "Compiler Agent", "role": "编译中", "avatar": "C", "color": "#7c3aed"},
    "Reviewer": {"agent": "Reviewer Agent", "role": "评审中", "avatar": "R", "color": "#d97706"},
    "Writer": {"agent": "Writer Agent", "role": "写入中", "avatar": "W", "color": "#16a34a"},
    "SYSTEM": {"agent": "Workflow", "role": "执行中", "avatar": "WF", "color": "#6b7280"},
}


def _build_canvas_tool_gateway(knowledge: GBrainKnowledge, tenant_id: str) -> ToolGateway:
    """构建只读 Canvas Tool Gateway；提案捕获不在此注册。"""

    secret = os.getenv("PI_TOOL_GATEWAY_SECRET") or f"evocanvas-tool-gateway:{tenant_id}:{uuid4().hex}"
    gateway = ToolGateway(RunScopedTokenCodec(secret))

    def material_read(context):
        material_id = str(context.arguments.get("material_id", "")).strip()
        material = global_materials_cache.get(material_id)
        if material is None:
            return {
                "status": "failed",
                "summary": "material was not found",
                "error": {"error_code": "source_not_found", "message": f"material {material_id} was not found"},
            }
        return {
            "status": "succeeded",
            "summary": "material read",
            "data": {
                "material_id": material_id,
                "filename": material.get("filename", material_id),
                "content": str(material.get("content", "")),
            },
            "source_refs": [material_id],
        }

    def source_resolve(context):
        source_ref_id = str(context.arguments.get("source_ref_id", "")).strip()
        source_ref = global_source_refs_cache.get(source_ref_id)
        if source_ref is None:
            return {
                "status": "failed",
                "summary": "source reference was not found",
                "error": {"error_code": "source_not_found", "message": f"source {source_ref_id} was not found"},
            }
        return {
            "status": "succeeded",
            "summary": "source reference resolved",
            "data": {
                "source_ref_id": source_ref_id,
                "display_name": source_ref.get("display_name", source_ref_id),
                "snapshot": dict(source_ref.get("snapshot", {})),
            },
            "source_refs": [source_ref_id],
        }

    def knowledge_retrieve(context):
        query = str(context.arguments.get("query", "")).strip()
        if not query:
            return {
                "status": "failed",
                "summary": "knowledge query is empty",
                "error": {"error_code": "invalid_request", "message": "query is required"},
            }
        return {
            "status": "succeeded",
            "summary": "knowledge retrieved",
            "data": knowledge.retrieve(query, context.arguments.get("scope")),
            "source_refs": [f"knowledge:{query[:80]}"],
        }

    def structure_validate(context):
        proposal = context.arguments.get("proposal")
        violations: list[str] = []
        if not isinstance(proposal, dict):
            violations.append("proposal must be an object")
        else:
            operations = proposal.get("operations")
            if not isinstance(operations, list):
                violations.append("proposal.operations must be an array")
            elif len(operations) > 128:
                violations.append("proposal.operations exceeds the 128 operation limit")
        return {
            "status": "succeeded",
            "summary": "structure validated" if not violations else "structure validation failed",
            "data": {"passed": not violations, "violations": violations},
        }

    for name, handler, allowed_run_kinds in (
        ("material.read", material_read, ("chat", "convergence")),
        ("source.resolve", source_resolve, ("chat", "convergence")),
        ("knowledge.retrieve", knowledge_retrieve, ("chat", "convergence")),
        ("structure.validate", structure_validate, ("convergence",)),
    ):
        gateway.register(
            name=name,
            version="v1",
            allowed_run_kinds=allowed_run_kinds,
            side_effect="none" if name == "structure.validate" else "read",
            timeout_seconds=5,
            handler=handler,
        )
    return gateway


def build_default_task_service(
    root: Path | None = None,
    canvas_execution: Any | None = None,
    tenant_id: str = "default",
) -> TaskService:
    """初始化并构建默认的任务服务 (TaskService)。

    该服务在系统启动或租户接入时动态实例化，绑定文件存储、知识检索库和
    Pi Canvas 执行边界。旧任务 WorkflowEngine 只在旧任务 API 真正执行时懒加载。

    Args:
        root (Optional[Path]): 任务持久化存储的根路径。若不提供，则使用系统临时目录下的兜底路径。

    Returns:
        TaskService: 初始化完成的任务服务控制面实例。
    """
    # 绑定存储后端与事件总线
    storage = FakeStorage(root or Path(tempfile.gettempdir()) / "manual-agent-phase1", event_bus=global_event_bus)
    project_root = Path(__file__).parent.parent.parent
    knowledge = GBrainKnowledge(str(project_root))
    tool_service = ToolService.default(root=storage, knowledge=knowledge)
    canvas_tool_gateway = _build_canvas_tool_gateway(knowledge, tenant_id)
    
    def build_legacy_engine():
        """仅在旧任务 API 被调用时创建旧 Provider 与 WorkflowEngine。"""

        from dotenv import load_dotenv
        from app.services.llm import OpenAILLM
        from app.workflows.engine import WorkflowEngine

        load_dotenv()
        api_key = os.getenv("API_KEY") or os.getenv("CRS_OAI_KEY") or ""
        base_url = os.getenv("BASE_URL") or "https://api.openai.com/v1"
        llm = OpenAILLM(api_key=api_key, base_url=base_url)
        return WorkflowEngine(tool_service=tool_service, llm=llm, storage=storage)

    engine = LazyLegacyWorkflowEngine(build_legacy_engine)
    peer_adapter = PeerAdapterService()
    peer_adapter.register_adapter("codex", CodexCLIHandler(workspace_root=project_root))
    return TaskService(
        registry=build_task_registry(),
        engine=engine,
        storage=storage,
        peer_adapter=peer_adapter,
        canvas_execution=canvas_execution,
        canvas_tool_gateway=canvas_tool_gateway,
        tenant_id=tenant_id,
        knowledge=knowledge,
    )


# 租户服务映射表，按租户 ID 隔离其各自的 TaskService 实例
_tenant_services = {}
# 测试状态下的全局 Mock/Stub 任务服务
_test_service = None

def get_task_service(tenant_id: str = Depends(get_tenant_workspace)):
    """FastAPI 依赖注入项：基于租户的身份隔离，获取或创建对应的 TaskService 实例。

    Args:
        tenant_id (str): 由 auth.py 中的 get_tenant_workspace 解析得到的隔离工作空间名称。

    Returns:
        TaskService: 该租户独立拥有的任务服务实例。
    """
    if _test_service:
        return _test_service
    if tenant_id not in _tenant_services:
        import tempfile
        from pathlib import Path
        # 基于租户 ID 创建隔离的存储子目录
        base_dir = Path(tempfile.gettempdir()) / "manual-agent-phase1" / tenant_id
        _tenant_services[tenant_id] = build_default_task_service(base_dir, tenant_id=tenant_id)
    return _tenant_services[tenant_id]


def get_canvas_service(service: TaskService = Depends(get_task_service)) -> CanvasService:
    """基于当前租户的存储与私有 Pi Runtime 构建 CanvasService。"""

    execution = getattr(service, "canvas_execution", None)
    if execution is None:
        try:
            timeout_seconds = max(0.001, int(os.getenv("PI_RUNTIME_TIMEOUT_MS", "30000")) / 1000)
        except ValueError:
            timeout_seconds = 30.0
        execution = PiRuntimeClient(
            base_url=os.getenv("PI_RUNTIME_URL", "http://127.0.0.1:8790"),
            internal_secret=os.getenv("PI_RUNTIME_INTERNAL_SECRET"),
            timeout_seconds=timeout_seconds,
        )
    return CanvasService(
        storage=service.storage,
        execution=execution,
        tool_gateway=getattr(service, "canvas_tool_gateway", None),
        tenant_id=getattr(service, "tenant_id", "default"),
    )


def create_app(task_service: TaskService | None = None):
    """构建并配置主 FastAPI 应用程序实例。

    注册所有路由控制、跨域中间件 (CORS)，以及任务生命周期管理相关的 API 端点。

    Args:
        task_service (Optional[TaskService]): 传入的特定任务服务，主要用于测试插桩。

    Returns:
        FastAPI: 配置完毕的 FastAPI 应用对象。

    Raises:
        RuntimeError: 当运行环境未安装 FastAPI 库时抛出。
    """
    global _test_service
    _test_service = task_service
    if FastAPI is None:
        raise RuntimeError("fastapi is required to create the HTTP app")
    
    app = FastAPI(title="PM-Agent Platform API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:4000",
            "http://127.0.0.1:4000",
            "http://localhost:4001",
            "http://127.0.0.1:4001",
            "http://localhost:4002",
            "http://127.0.0.1:4002",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health(service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """健康检查接口，确认后端服务处于可用状态。

        Args:
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 包含服务状态与版本的字典。
        """
        return {"status": "ok", "service": "pm-agent-backend", "version": "0.1.0"}

    @app.post("/internal/v1/tool-calls")
    async def internal_tool_call(
        request: Request,
        payload: Dict[str, Any],
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        """Pi Runtime 使用的内部只读工具入口；浏览器和普通 API 不应调用。"""

        gateway = getattr(service, "canvas_tool_gateway", None)
        authorization = request.headers.get("authorization", "")
        token = authorization[len("Run "):].strip() if authorization.startswith("Run ") else ""
        if gateway is None or not token:
            return JSONResponse(
                status_code=401,
                content={
                    "schema_version": "pi-runtime.tool-result.v1",
                    "tool_call_id": str(payload.get("tool_call_id", "")),
                    "status": "denied",
                    "summary": "internal Tool Gateway authorization is required",
                    "source_refs": [],
                    "artifacts": [],
                    "error": {
                        "schema_version": "pi-runtime.error.v1",
                        "error_code": "permission_denied",
                        "category": "permission_denied",
                        "message": "internal Tool Gateway authorization is required",
                        "retryable": False,
                        "details": {},
                    },
                    "completed_at": "",
                },
            )
        try:
            return await gateway.invoke(token, payload)
        except ToolGatewayError as exc:
            return JSONResponse(
                status_code=403 if exc.category == "permission_denied" else 400,
                content={
                    "schema_version": "pi-runtime.tool-result.v1",
                    "tool_call_id": str(payload.get("tool_call_id", "")),
                    "status": "denied",
                    "summary": str(exc),
                    "source_refs": [],
                    "artifacts": [],
                    "error": {
                        "schema_version": "pi-runtime.error.v1",
                        "error_code": exc.code,
                        "category": exc.category,
                        "message": str(exc),
                        "retryable": False,
                        "details": {},
                    },
                    "completed_at": "",
                },
            )

    @app.get("/api/knowledge/health")
    async def knowledge_health(service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """检查底层知识库服务的可用性与连通性。

        Args:
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 包含健康状态、检索项数量及错误信息的字典。
        """
        knowledge = getattr(service, "knowledge", None)
        if knowledge is None:
            knowledge = getattr(getattr(service.engine, "tool_service", None), "knowledge_backend", None)
        # 如果知识库正常，尝试通过检索关键词验证接口
        data = knowledge.retrieve("WorkflowEngine TaskDefinition ToolService") if knowledge else {"degraded": True, "items": [], "error": "knowledge backend unavailable"}
        return {
            "status": "degraded" if data.get("degraded") else "ok",
            "items": len(data.get("items", [])),
            "error": data.get("error"),
        }

    @app.get("/api/canvas/workspaces/{workspace_id}")
    async def get_canvas_workspace(
        workspace_id: str,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        workspace = canvas_service.get_workspace(workspace_id)
        return workspace.to_dict()

    @app.patch("/api/canvas/workspaces/{workspace_id}")
    async def patch_canvas_workspace(
        workspace_id: str,
        payload: Dict[str, Any],
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        return canvas_service.patch_workspace(workspace_id, payload)

    @app.get("/api/canvas/workspaces")
    async def list_canvas_workspaces(
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        return canvas_service.list_recent_workspaces()

    @app.get("/api/canvas/workspaces/{workspace_id}/canvas")
    async def get_canvas_view(
        workspace_id: str,
        snapshot_id: Optional[str] = None,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        try:
            return canvas_service.get_canvas_view(workspace_id, snapshot_id=snapshot_id)
        except CanvasSnapshotNotFoundError:
            raise HTTPException(status_code=404, detail="canvas snapshot not found")

    @app.post("/api/canvas/workspaces/{workspace_id}/messages")
    async def post_canvas_message(
        workspace_id: str,
        request: CanvasMessageRequest,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        try:
            return await canvas_service.run_pi_turn(
                workspace_id=workspace_id,
                message=request.message,
                selected_card_ids=list(request.selected_card_ids),
                material_ids=list(request.material_ids),
                source_ref_ids=list(request.source_ref_ids),
                model=request.model,
            )
        except CanvasTurnInProgressError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "workspace_id": workspace_id,
                    "reason": "turn_in_progress",
                    "message": "当前工作区仍有一轮处理中，请等待本轮结束后再继续提交。",
                    "active_turn": exc.active_turn,
                },
            )
        except CanvasMessageValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except PackageVersionStaleError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "workspace_id": workspace_id,
                    "reason": "stale",
                    "error_code": PackageVersionStaleError.code,
                    "message": str(exc),
                },
            )
        except PiRuntimeUnknownError as exc:
            return JSONResponse(
                status_code=503,
                content={
                    "workspace_id": workspace_id,
                    "reason": "runtime_unknown",
                    "error_code": exc.error_code,
                    "run_id": exc.run_id,
                    "message": str(exc),
                    "retry_same_run_id": bool(exc.details.get("retry_same_run_id")),
                },
            )
        except PiRuntimeError as exc:
            return JSONResponse(
                status_code=502,
                content={
                    "workspace_id": workspace_id,
                    "reason": "runtime_error",
                    "error_code": exc.error_code,
                    "run_id": exc.run_id,
                    "message": str(exc),
                },
            )

    @app.get("/api/canvas/workspaces/{workspace_id}/events")
    async def get_canvas_events(
        workspace_id: str,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ):
        async def stream():
            import asyncio
            import queue

            channel = canvas_service.event_stream_id(workspace_id)
            if hasattr(canvas_service.storage, "event_bus") and canvas_service.storage.event_bus:
                q = canvas_service.storage.event_bus.subscribe(channel)
                try:
                    while True:
                        try:
                            event = q.get_nowait()
                            yield f"id: {event.id}\nevent: {event.type}\ndata: {json.dumps(event.to_dict(), ensure_ascii=False)}\n\n"
                            if event.type in {"canvas.turn.completed", "canvas.turn.failed"}:
                                break
                        except queue.Empty:
                            await asyncio.sleep(0.1)
                finally:
                    canvas_service.storage.event_bus.unsubscribe(channel, q)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/canvas/workspaces/{workspace_id}/snapshots")
    async def list_canvas_snapshots(
        workspace_id: str,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        return canvas_service.list_snapshots(workspace_id)

    @app.post("/api/canvas/workspaces/{workspace_id}/snapshots")
    async def create_canvas_snapshot(
        workspace_id: str,
        request: CanvasSnapshotCreateRequest,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        return canvas_service.create_snapshot(
            workspace_id=workspace_id,
            title=request.title,
            summary=request.summary,
        )

    @app.get("/api/canvas/workspaces/{workspace_id}/handoff")
    async def get_canvas_handoff(
        workspace_id: str,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        return canvas_service.get_handoff(workspace_id)

    @app.get("/api/canvas/workspaces/{workspace_id}/messages")
    async def get_canvas_messages(
        workspace_id: str,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        """读取 Canvas 对话消息；消息正文仍以 Python 仓储为唯一事实源。"""

        return canvas_service.get_chat_messages(workspace_id)

    @app.post("/api/canvas/workspaces/{workspace_id}/handoff/refresh")
    async def refresh_canvas_handoff(
        workspace_id: str,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        try:
            return canvas_service.refresh_handoff(workspace_id)
        except CanvasTurnInProgressError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "workspace_id": workspace_id,
                    "reason": "turn_in_progress",
                    "message": "当前工作区仍有一轮处理中，请等待本轮结束后再刷新交接物。",
                    "active_turn": exc.active_turn,
                },
            )

    @app.patch("/api/canvas/workspaces/{workspace_id}/cards/{card_id}")
    async def patch_canvas_card(
        workspace_id: str,
        card_id: str,
        request: CanvasCardPatchRequest,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        payload = request.model_dump(exclude_none=True) if hasattr(request, "model_dump") else request.dict(exclude_none=True)
        try:
            return canvas_service.patch_card(workspace_id, card_id, payload)
        except CanvasCardConfirmationRequiredError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "workspace_id": workspace_id,
                    "card_id": card_id,
                    "reason": "chat_confirmation_required",
                    "message": str(exc),
                },
            )
        except CanvasCardNotFoundError:
            raise HTTPException(status_code=404, detail="canvas card not found")

    @app.get("/api/canvas/workspaces/{workspace_id}/confirmations")
    async def list_canvas_confirmations(
        workspace_id: str,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        # L3 规格已下线独立确认队列：高影响提案的确认/拒绝统一通过普通 Chat 消息触发，
        # 不再提供独立的只读确认列表路由，避免形成第二条状态通道。
        raise HTTPException(status_code=404, detail="confirmation queue removed")

    @app.post("/api/canvas/workspaces/{workspace_id}/cards")
    async def create_canvas_card(
        workspace_id: str,
        request: CanvasCardCreateRequest,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        try:
            return canvas_service.create_card(
                workspace_id=workspace_id,
                kind=request.kind,
                title=request.title,
                summary=request.summary,
                tags=request.tags,
                source_refs=request.source_refs,
                metadata=request.metadata,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.delete("/api/canvas/workspaces/{workspace_id}/cards/{card_id}")
    async def delete_canvas_card(
        workspace_id: str,
        card_id: str,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        try:
            return canvas_service.delete_card(workspace_id, card_id)
        except CanvasCardNotFoundError:
            raise HTTPException(status_code=404, detail="canvas card not found")

    @app.post("/api/canvas/workspaces/{workspace_id}/relations")
    async def create_canvas_relation(
        workspace_id: str,
        request: CanvasRelationCreateRequest,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        try:
            return canvas_service.create_relation(
                workspace_id=workspace_id,
                kind=request.kind,
                from_card_id=request.from_card_id,
                to_card_id=request.to_card_id,
                note=request.note,
                metadata=request.metadata,
            )
        except CanvasRelationValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.delete("/api/canvas/workspaces/{workspace_id}/relations/{relation_id}")
    async def delete_canvas_relation(
        workspace_id: str,
        relation_id: str,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        try:
            return canvas_service.delete_relation(workspace_id, relation_id)
        except CanvasRelationNotFoundError:
            raise HTTPException(status_code=404, detail="canvas relation not found")

    @app.post("/api/canvas/workspaces/{workspace_id}/cards/{card_id}/move")
    async def move_canvas_card(
        workspace_id: str,
        card_id: str,
        request: CanvasCardMoveRequest,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        try:
            return canvas_service.move_card(
                workspace_id=workspace_id,
                card_id=card_id,
                stage=request.stage,
                reason=request.reason,
            )
        except CanvasCardNotFoundError:
            raise HTTPException(status_code=404, detail="canvas card not found")

    @app.get("/api/canvas/workspaces/{workspace_id}/todos")
    async def get_canvas_todos(
        workspace_id: str,
        snapshot_id: Optional[str] = None,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        try:
            return canvas_service.get_todos(workspace_id, snapshot_id=snapshot_id)
        except CanvasSnapshotNotFoundError:
            raise HTTPException(status_code=404, detail="canvas snapshot not found")

    @app.post("/api/tasks")
    async def create_task(request: CreateTaskRequest, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """根据客户端的 DTO 参数创建新任务，并异步基于任务目标提炼精简的任务标题。

        Args:
            request (CreateTaskRequest): 创建任务所需的负载参数。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 包含任务唯一 ID 及其初始状态的字典。

        Raises:
            HTTPException: 当参数校验不通过 (ValueError) 时抛出 400 错误。
        """
        payload = request.model_dump(exclude_none=True) if hasattr(request, "model_dump") else request.dict(exclude_none=True)  # Pydantic v1/v2 兼容
        normalized = _normalize_create_payload(payload)
        try:
            task = service.create_task(normalized.pop("type"), normalized)
            
            def update_title_async():
                # 提取有意义的提示文本作为标题提炼的输入
                prompt = (
                    payload.get("prompt")
                    or payload.get("goal")
                    or payload.get("business_goal")
                    or payload.get("business_intent")
                    or ""
                ).strip()
                if not prompt: return
                # 异步调用 LLM 自动将长文本简化为 10 字以内的小标题
                res = service.engine.llm.invoke("System", f"请为以下任务目标取一个精简的名字（不超过10个字），直接输出名字本身，不要带标点和前缀：\n{prompt[:500]}", {})
                if res.content and not "失败" in res.content:
                    new_title = res.content.strip(' "”\'\n').strip()
                    if new_title:
                        t = service.get_task(task.task_id)
                        t.context.title = new_title
                        service.storage.save_task(t)

            # 启动守护线程执行标题异步提炼，避免阻塞主 API 请求
            threading.Thread(target=update_title_async, daemon=True).start()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"task_id": task.task_id, "taskId": task.task_id, "id": task.task_id, "status": task.status.value}

    @app.post("/api/tasks/{task_id}/peer-result")
    async def submit_peer_result(
        task_id: str,
        payload: Dict[str, Any] = Body(...),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        """接收 AI 技术同事回传的 result bundle，并推进 repair -> review 闭环。"""
        try:
            result_task = service.complete_peer_collaboration(task_id, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="task not found") from exc

        response = {
            "task_id": task_id,
            "status": "completed",
            "delivery_bundle_recorded": True,
            "followup_review_id": None,
        }
        if result_task.definition.type == "acceptance_review":
            response["followup_review_id"] = result_task.task_id
            response["followup_review_status"] = result_task.status.value
        else:
            response["result_task_id"] = result_task.task_id
            response["result_task_status"] = result_task.status.value
        return response

    @app.post("/api/tasks/{task_id}/peer-dispatch")
    async def dispatch_peer_collaboration(
        task_id: str,
        payload: Dict[str, Any] = Body(default={}),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        """根据任务内的 agent package 与 peer_target 主动派发 AI 技术同事协作。"""
        try:
            result_task = service.start_peer_collaboration(task_id, payload.get("peer_target"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="task not found") from exc

        refreshed = service.get_task(task_id)
        delivery_bundle = dict(refreshed.context.inputs.get("delivery_bundle") or {})
        response = {
            "task_id": task_id,
            "status": "completed",
            "peer_target": delivery_bundle.get("peer_target") or payload.get("peer_target"),
            "delivery_bundle_recorded": bool(delivery_bundle),
        }
        if result_task.definition.type == "acceptance_review":
            response["followup_review_id"] = result_task.task_id
            response["followup_review_status"] = result_task.status.value
        else:
            response["result_task_id"] = result_task.task_id
            response["result_task_status"] = result_task.status.value
        return response

    @app.get("/api/tasks")
    async def list_tasks(service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """列出所有未被软删除的任务列表（转换为前端特有的扁平 DTO 模型）。

        Args:
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 前端任务对象列表。
        """
        return {"tasks": [_frontend_task(item) for item in service.storage.list_tasks(service.registry) if not getattr(item, "is_deleted", False)]}

    @app.get("/api/work-items")
    async def list_work_items(service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """获取所有未被软删除的工作项列表（后端标准数据模型）。

        Args:
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 后端标准工作项字典列表。
        """
        tasks = [
            item for item in service.storage.list_tasks(service.registry)
            if not getattr(item, "is_deleted", False)
        ]
        return {
            "work_items": [
                service.get_work_item(task.task_id).to_dict()
                for task in tasks
            ]
        }

    @app.get("/api/work-items/{work_id}")
    async def get_work_item(work_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """获取指定工作项的详细信息。

        Args:
            work_id (str): 目标工作项/任务的 ID。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 工作项的字典结构。
        """
        _load_task_or_404(service, work_id)
        return service.get_work_item(work_id).to_dict()

    @app.get("/api/work-items/{work_id}/product-context")
    async def get_work_item_product_context(work_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """获取特定工作项的产品上下文 (ProductContext)。

        Args:
            work_id (str): 目标任务 ID。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 产品上下文的序列化字典。
        """
        _load_task_or_404(service, work_id)
        return service.get_product_context(work_id).to_dict()

    @app.get("/api/work-items/{work_id}/artifact-graph")
    async def get_work_item_artifact_graph(work_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """获取特定工作项对应的产物血缘/依赖图 (ArtifactGraph)。

        Args:
            work_id (str): 目标任务 ID。
            service (TaskService): 依赖注入的任务 management 服务实例。

        Returns:
            Dict[str, Any]: 产物图的序列化字典。
        """
        _load_task_or_404(service, work_id)
        return service.get_artifact_graph(work_id).to_dict()

    @app.get("/api/tasks/{task_id}")
    async def get_task(task_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """获取任务当前的简要详情，用于前端列表展示。

        Args:
            task_id (str): 目标任务 ID。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 前端任务对象格式的数据。
        """
        task = _load_task_or_404(service, task_id)
        return _frontend_task(task)

    @app.post("/api/tasks/{task_id}/run")
    async def run_task(task_id: str, background_tasks: BackgroundTasks, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """异步启动或恢复执行指定的任务。

        使用 FastAPI 的 BackgroundTasks 机制，防止 HTTP 连接由于长时间的大模型调用而超时。

        Args:
            task_id (str): 目标任务 ID。
            background_tasks (BackgroundTasks): FastAPI 后台任务管理器。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 包含任务状态及所卡在步骤的字典。
        """
        task = _load_task_or_404(service, task_id)
        background_tasks.add_task(service.run_task, task_id)
        return {"task_id": task.task_id, "taskId": task.task_id, "status": task.status.value, "waiting_step_id": task.waiting_step_id}

    @app.post("/api/tasks/{task_id}/interrupt")
    async def interrupt_task(task_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """中断正在运行的任务工作流。

        Args:
            task_id (str): 目标任务 ID。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 包含被中断任务 ID 与状态的字典。
        """
        _load_task_or_404(service, task_id)
        task = service.cancel_task(task_id)
        return {"task_id": task.task_id, "taskId": task.task_id, "status": task.status.value}

    @app.delete("/api/tasks/{task_id}")
    async def delete_task(task_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """软删除指定的任务（移至回收站）。

        Args:
            task_id (str): 目标任务 ID。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 包含已删除任务 ID 及其状态。
        """
        task = _load_task_or_404(service, task_id)
        service.delete_task(task_id)
        return {"id": task.task_id, "status": "deleted"}

    @app.get("/api/tasks/{task_id}/events")
    async def get_events(task_id: str, service: TaskService = Depends(get_task_service)):
        """流式获取指定任务的执行事件（基于 SSE，Server-Sent Events）。

        先重放历史事件，再基于全局事件总线订阅并监听任务运行期间的实时事件，
        直到任务运行结束（如完成、失败或取消）后断开连接。

        Args:
            task_id (str): 目标任务 ID。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            StreamingResponse: SSE 事件响应流。
        """
        _load_task_or_404(service, task_id)

        async def stream():
            import asyncio
            import queue
            # 1. 恢复并重放磁盘或内存中已记录的历史事件
            for event in service.storage.read_events(task_id):
                data = event.to_dict()
                data["frontend_message"] = _event_to_frontend_message(data)
                yield f"id: {event.id}\nevent: {event.type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                
            # 2. 订阅事件总线以监听后续实时生成的事件
            if hasattr(service.storage, "event_bus") and service.storage.event_bus:
                q = service.storage.event_bus.subscribe(task_id)
                try:
                    while True:
                        try:
                            event = q.get_nowait()
                            data = event.to_dict()
                            data["frontend_message"] = _event_to_frontend_message(data)
                            yield f"id: {event.id}\nevent: {event.type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                            # 任务终结状态下主动跳出流循环
                            if event.type in {"task.completed", "task.cancelled", "task.failed"}:
                                break
                        except queue.Empty:
                            # 无新事件时短暂休眠，避免死循环占用 CPU
                            await asyncio.sleep(0.1)
                finally:
                    service.storage.event_bus.unsubscribe(task_id, q)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/tasks/{task_id}/messages")
    async def get_task_messages(task_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """获取指定任务已发生的聊天式对话消息历史。

        过滤掉底层的 typing 思考状态事件，以便前端直接渲染对话面板。

        Args:
            task_id (str): 目标任务 ID。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 对话消息对象列表。
        """
        _load_task_or_404(service, task_id)
        messages = [_event_to_frontend_message(event.to_dict()) for event in service.storage.read_events(task_id)]
        return {"messages": [message for message in messages if message and message.get("type") != "typing"]}

    @app.post("/api/tasks/{task_id}/decisions")
    async def apply_decision(task_id: str, request: DecisionRequest, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """为当前因 DecisionGate (裁决门禁) 暂停的任务提报用户裁决决策。

        包含情绪拦截调停机制，当前端判定用户情绪有挫折感时，自动追加调停 prompt。

        Args:
            task_id (str): 目标任务 ID'].
            request (DecisionRequest): 用户提报的决策负载。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 包含任务 ID 与新状态的字典。
        """
        _load_task_or_404(service, task_id)
        
        # 拦截用户极端负面情绪并执行调停 prompt 注入
        from app.cli.utils import intercept_user_emotion
        request.decision = intercept_user_emotion(request.decision or "")
            
        task = service.apply_decision(
            task_id,
            request.decision,
            request.selected_option,
            request.quoted_selections,
        )
        return {"task_id": task.task_id, "taskId": task.task_id, "status": task.status.value}

    @app.get("/api/tasks/{task_id}/artifacts")
    async def list_artifacts(task_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """获取指定任务已生成的所有产物元数据列表。

        Args:
            task_id (str): 目标任务 ID。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 产物对象列表。
        """
        _load_task_or_404(service, task_id)
        return {"artifacts": [artifact.to_dict() for artifact in service.storage.list_artifacts(task_id)]}

    @app.get("/api/tasks/{task_id}/trace")
    async def get_task_trace(task_id: str, service: TaskService = Depends(get_task_service)):
        """获取任务执行期间的所有 Agent 调用与工具调用的分布式 Trace 树结构。

        用于在前端展示层级可视化的调用调用链路，遵循 L1/L2 精简收纳原则。

        Args:
            task_id (str): 目标任务 ID。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 树状结构的 Trace 根节点。
        """
        _load_task_or_404(service, task_id)
        events = list(service.storage.read_events(task_id))
        
        # 构建 Trace 树的根节点
        root_span = {
            "span_id": task_id,
            "name": "Task Execution",
            "type": "task",
            "children": []
        }
        
        current_step_span = None
        for event in events:
            if event.type == "workflow.step.started":
                # 当工作流步骤开始时，创建一个步骤 Span
                current_step_span = {
                    "span_id": event.payload.get("step_id", event.id),
                    "name": f"Step: {event.role}",
                    "type": "workflow_step",
                    "attributes": event.payload,
                    "children": []
                }
                root_span["children"].append(current_step_span)
            elif event.type.startswith("tool.call"):
                # 工具调用作为子节点挂载到当前步骤 Span 之下，若无当前步骤则直接挂在根下
                tool_span = {
                    "span_id": event.id,
                    "name": f"Tool: {event.payload.get('tool_name')}",
                    "type": "tool_call",
                    "attributes": event.payload,
                }
                if current_step_span:
                    current_step_span["children"].append(tool_span)
                else:
                    root_span["children"].append(tool_span)
                    
        return root_span

    @app.get("/api/tasks/{task_id}/document")
    async def get_task_document(task_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """获取指定任务的最新主要文档产物内容（若尚未生成则返回引导性的初始化内容）。

        Args:
            task_id (str): 目标任务 ID。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 包含主要文档内容的字典。
        """
        task = _load_task_or_404(service, task_id)
        artifacts = service.storage.list_artifacts(task_id)
        artifact = artifacts[-1] if artifacts else None
        if not artifact:
            # 尚未生成文档时的前端降级预览文本
            content = f"# {task.context.title}\n\n任务已创建，文档产物将在 Workflow 完成后生成。\n"
            return {"task_id": task_id, "taskId": task_id, "artifact_id": None, "artifactId": None, "content": content, "title": task.context.title}
        full = service.storage.read_artifact(artifact.artifact_id)
        return {
            "task_id": task_id,
            "taskId": task_id,
            "artifact_id": full.artifact_id,
            "artifactId": full.artifact_id,
            "name": full.name,
            "version": full.version,
            "title": task.context.title,
            "content": full.content or "",
        }

    @app.put("/api/tasks/{task_id}/document")
    async def update_task_document(task_id: str, payload: Dict[str, Any] = Body(...), service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """更新（覆盖）指定任务的主要文档产物内容，并在写入前自动备份历史版本。

        Args:
            task_id (str): 目标任务 ID。
            payload (Dict[str, Any]): 包含新文档内容的字典。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 更新后的产物详情。
        """
        task = _load_task_or_404(service, task_id)
        artifacts = service.storage.list_artifacts(task_id)
        if not artifacts:
            # 如先前无文档，新建一个主要 Markdown 文档
            name = task.definition.output_spec.get("primary_artifact", "document.md")
            artifact = service.storage.write_artifact(task_id, name, payload.get("content", ""), created_by="user")
        else:
            # 备份并写入新版本
            service.storage.backup_artifact(artifacts[-1].artifact_id)
            artifact = service.storage.update_artifact(artifacts[-1].artifact_id, payload.get("content", artifacts[-1].content or ""), updated_by="user")
        return {"artifact_id": artifact.artifact_id, "artifactId": artifact.artifact_id, "version": artifact.version, "content": artifact.content or ""}

    @app.get("/api/artifacts/{artifact_id}")
    async def get_artifact(artifact_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """读取指定唯一标识的产物详细内容。

        Args:
            artifact_id (str): 产物唯一标识。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 产物详细内容的字典。

        Raises:
            HTTPException: 当找不到对应产物时抛出 404 错误。
        """
        try:
            return service.storage.read_artifact(artifact_id).to_dict(include_content=True)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="artifact not found") from exc

    @app.put("/api/artifacts/{artifact_id}")
    async def update_artifact(artifact_id: str, payload: Dict[str, Any] = Body(...), service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """覆盖更新指定标识的产物内容，并备份旧版本。

        Args:
            artifact_id (str): 产物唯一标识。
            payload (Dict[str, Any]): 包含更新内容的字典。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 更新后产物的详细元数据。

        Raises:
            HTTPException: 当找不到对应产物时抛出 404 错误。
        """
        try:
            service.storage.backup_artifact(artifact_id)
            updated = service.storage.update_artifact(artifact_id, payload.get("content", ""), updated_by="user")
            return updated.to_dict(include_content=True)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="artifact not found") from exc

    @app.post("/api/materials", response_model=MaterialUploadResponse)
    async def upload_material(file: UploadFile = File(...), service: TaskService = Depends(get_task_service)) -> MaterialUploadResponse:
        """上传当前工作区资料，写入材料层而不是直接写入知识库。

        Args:
            file (UploadFile): 上传的多媒体/文本文件。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            MaterialUploadResponse: 材料上传响应模型。
        """
        content = await file.read()
        text_content = content.decode("utf-8", errors="ignore")
        material_id = f"material_{uuid4().hex[:12]}"
        global_materials_cache[material_id] = {
            "filename": file.filename,
            "content": text_content,
            "layer": "material",
            "display_name": file.filename,
        }
        return MaterialUploadResponse(
            material_id=material_id,
            status="uploaded",
            summary=f"{file.filename} 已进入当前工作区资料层，后续会参与输入编译，不会自动进入知识库。",
            display_name=file.filename,
        )

    @app.get("/api/materials/{material_id}")
    async def get_material(material_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """读取指定材料层对象的脱敏元数据。"""

        del service
        item = global_materials_cache.get(material_id)
        if not item:
            raise HTTPException(status_code=404, detail="material not found")
        return {
            "material_id": material_id,
            "layer": item.get("layer", "material"),
            "display_name": item.get("display_name") or item.get("filename") or "未命名资料",
            "summary": f"{item.get('display_name') or item.get('filename') or '资料'} 已绑定到当前工作区。",
        }

    @app.get("/api/knowledge")
    async def list_knowledge(service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        return {"items": _knowledge_items()}

    @app.post("/api/knowledge")
    async def create_knowledge(payload: Dict[str, Any] = Body(...), service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        item = {
            "id": f"kb_{uuid4().hex[:8]}",
            "type": payload.get("type", "doc"),
            "title": payload.get("title", "未命名知识"),
            "desc": payload.get("desc", "已提交到候选知识区，等待后续解析入库。"),
            "tags": payload.get("tags", []),
            "updated": "刚刚",
            "author": payload.get("author", "User"),
        }
        return item

    @app.get("/api/knowledge/candidates")
    async def list_knowledge_candidates(service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """列出等待审核的知识候选条目。"""

        del service
        return {"items": list(global_knowledge_candidates_cache.values())}

    @app.post("/api/knowledge/candidates")
    async def create_knowledge_candidate(
        payload: KnowledgeCandidateCreateRequest,
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        """写入知识候选区，等待后续审核后再升级为正式知识。"""

        del service
        item = {
            "id": f"kbc_{uuid4().hex[:8]}",
            "type": payload.type or "doc",
            "title": payload.title,
            "desc": payload.desc or "来自工作区产出或资料抽取的候选知识，等待审核。",
            "tags": list(payload.tags or []),
            "author": payload.author or "Canvas AI",
            "status": "candidate",
            "updated": "刚刚",
            "source_artifact_id": payload.source_artifact_id,
            "source_workspace_id": payload.source_workspace_id,
        }
        global_knowledge_candidates_cache[item["id"]] = item
        return item

    @app.post("/api/knowledge/{knowledge_id}/approve")
    async def approve_knowledge(
        knowledge_id: str,
        payload: Optional[Dict[str, Any]] = Body(None),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        """将候选知识审核通过并升级为正式知识条目。"""

        del service
        candidate = global_knowledge_candidates_cache.get(knowledge_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="knowledge candidate not found")
        approved = {
            "id": f"kb_{uuid4().hex[:8]}",
            "type": payload.get("type", candidate.get("type", "doc")) if payload else candidate.get("type", "doc"),
            "title": (payload or {}).get("title", candidate.get("title", "未命名知识")),
            "desc": (payload or {}).get("desc", candidate.get("desc", "")),
            "tags": (payload or {}).get("tags", candidate.get("tags", [])),
            "updated": "刚刚",
            "author": candidate.get("author", "Canvas AI"),
            "status": "approved",
            "source_candidate_id": knowledge_id,
        }
        global_knowledge_candidates_cache.pop(knowledge_id, None)
        return approved

    @app.get("/api/source-connectors")
    async def list_source_connectors(service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """返回可用于创建结构化数据引用的连接器清单。"""

        del service
        return {
            "items": [
                {
                    "id": "saved_query",
                    "label": "保存查询",
                    "description": "引用已保存 SQL 或查询模版，生成受控快照后参与输入编译。",
                },
                {
                    "id": "dashboard_metric",
                    "label": "指标看板",
                    "description": "引用 BI 看板指标与筛选条件，生成可追溯的数据证据卡。",
                },
                {
                    "id": "table_slice",
                    "label": "数据切片",
                    "description": "对表或视图做有限条件切片，只返回样本和聚合摘要。",
                },
            ]
        }

    @app.get("/api/source-refs")
    async def list_source_refs(service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """列出当前已创建的外部数据引用。"""

        del service
        return {"items": list(global_source_refs_cache.values())}

    @app.post("/api/source-refs")
    async def create_source_ref(
        payload: SourceRefCreateRequest,
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        """创建一个外部结构化数据引用，并生成首个只读快照摘要。"""

        del service
        source_ref_id = f"src_{uuid4().hex[:10]}"
        snapshot_id = f"snapshot_{uuid4().hex[:10]}"
        summary = _build_source_ref_summary(
            connector_type=payload.connector_type,
            display_name=payload.display_name,
            query_text=payload.query_text,
            metric_name=payload.metric_name,
            filters=payload.filters,
        )
        item = {
            "source_ref_id": source_ref_id,
            "layer": "source_ref",
            "connector_type": payload.connector_type,
            "display_name": payload.display_name,
            "workspace_id": payload.workspace_id,
            "query_text": payload.query_text,
            "metric_name": payload.metric_name,
            "filters": dict(payload.filters or {}),
            "snapshot": {
                "snapshot_id": snapshot_id,
                "captured_at": "刚刚",
                "summary": summary,
                "sample_rows": [],
                "aggregates": [],
            },
        }
        global_source_refs_cache[source_ref_id] = item
        return item

    @app.get("/api/source-refs/{source_ref_id}")
    async def get_source_ref(source_ref_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """读取指定数据引用及其最新快照摘要。"""

        del service
        item = global_source_refs_cache.get(source_ref_id)
        if not item:
            raise HTTPException(status_code=404, detail="source ref not found")
        return item

    @app.post("/api/source-refs/{source_ref_id}/snapshot")
    async def refresh_source_ref_snapshot(
        source_ref_id: str,
        payload: Optional[Dict[str, Any]] = Body(None),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        """显式刷新一个数据引用的只读快照。"""

        del service
        item = global_source_refs_cache.get(source_ref_id)
        if not item:
            raise HTTPException(status_code=404, detail="source ref not found")
        snapshot_id = f"snapshot_{uuid4().hex[:10]}"
        filters = (payload or {}).get("filters", item.get("filters", {}))
        item["filters"] = dict(filters or {})
        item["snapshot"] = {
            "snapshot_id": snapshot_id,
            "captured_at": "刚刚",
            "summary": _build_source_ref_summary(
                connector_type=item.get("connector_type", "saved_query"),
                display_name=item.get("display_name", "未命名数据引用"),
                query_text=item.get("query_text"),
                metric_name=item.get("metric_name"),
                filters=item.get("filters", {}),
            ),
            "sample_rows": [],
            "aggregates": [],
        }
        return item

    @app.get("/api/rules")
    async def list_rules(status: str = "pending", service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """获取提取出的产品规则白名单/黑名单列表。

        Args:
            status (str): 规则审核状态，默认为 'pending'。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 规则字典列表。
        """
        return {"rules": [rule for rule in _rule_items() if rule["status"] == status]}

    @app.post("/api/rules/{rule_id}/approve")
    async def approve_rule(rule_id: str, payload: Optional[Dict[str, Any]] = Body(None), service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """批准某条提取出的规则，将其归入已通过 (approved) 可信法则区。

        Args:
            rule_id (str): 规则唯一标识。
            payload (Optional[Dict[str, Any]]): 规则的具体修订内容。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 批准后的规则元数据。
        """
        p = payload or {}
        content = p.get("content") or p.get("desc") or p.get("title")
        return {"id": rule_id, "status": "approved", "content": content}

    @app.post("/api/rules/{rule_id}/reject")
    async def reject_rule(rule_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """拒绝某条提取出的规则，将其标记为已驳回 (rejected)。

        Args:
            rule_id (str): 规则唯一标识。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 被拒绝的规则元数据。
        """
        return {"id": rule_id, "status": "rejected"}

    @app.get("/api/recycle")
    async def list_recycle(service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """获取回收站内所有已被软删除的任务与文档列表。

        Args:
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 软删除项的对象列表，包含文件大小与删除时间。
        """
        tasks = service.storage.list_tasks(service.registry)
        deleted_tasks = [t for t in tasks if getattr(t, "is_deleted", False)]
        items = []
        for t in deleted_tasks:
            import os
            task_file = service.storage._task_dir(t.task_id) / "task.json"
            size = "N/A"
            if task_file.exists():
                size_kb = os.path.getsize(task_file) / 1024
                size = f"{size_kb:.1f} KB"
            items.append({
                "id": t.task_id,
                "name": t.context.title,
                "type": "task",
                "size": size,
                "deletedAt": _format_event_time(t.deleted_at) if getattr(t, "deleted_at", None) else "刚刚",
                "deletedBy": "User"
            })
        return {"items": items + _recycle_items()}

    @app.post("/api/recycle/{item_id}/restore")
    async def restore_recycle(item_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """从回收站中恢复已被软删除的任务。

        Args:
            item_id (str): 软删除项的唯一标识。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 恢复状态反馈。
        """
        if item_id.startswith("trash_"):
            return {"id": item_id, "status": "restored"}
        try:
            service.restore_task(item_id)
        except Exception:
            raise HTTPException(status_code=404, detail="task not found")
        return {"id": item_id, "status": "restored"}

    @app.delete("/api/recycle/{item_id}")
    async def delete_recycle(item_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """永久删除回收站中的指定任务（无法恢复）。

        Args:
            item_id (str): 软删除项的唯一标识。
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 删除状态反馈。
        """
        if item_id.startswith("trash_"):
            return {"id": item_id, "status": "deleted"}
        service.permanent_delete_task(item_id)
        return {"id": item_id, "status": "deleted"}

    @app.get("/api/conversations/recent")
    async def recent_conversations(service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
        """获取最近活跃的任务对话列表，并按时间线进行归类分组（今天、昨天、更早）。

        通过获取任务文件的最近修改时间、事件日志的写入时间以及文档改动时间，
        计算得出最准确的最后活跃时间并进行倒序排序。

        Args:
            service (TaskService): 依赖注入的任务管理服务实例。

        Returns:
            Dict[str, Any]: 按 "today", "yesterday", "older" 分组的最近任务列表。
        """
        import os
        from datetime import datetime, date
        tasks_data = []
        today_date = date.today()

        for task in service.storage.list_tasks(service.registry):
            if getattr(task, "is_deleted", False):
                continue
            
            task_dir = service.storage.root / "tasks" / task.task_id
            task_file = task_dir / "task.json"
            events_file = task_dir / "events.jsonl"
            
            if task_file.exists():
                stat = os.stat(task_file)
                # 基础时间：任务创建时间
                last_activity = getattr(stat, 'st_birthtime', stat.st_ctime)
                
                # 检查最新对话事件文件的写入时间
                if events_file.exists():
                    last_activity = max(last_activity, os.path.getmtime(events_file))
                
                # 检查最新文档改动文件的写入时间
                artifacts = service.storage.list_artifacts(task.task_id)
                if artifacts:
                    art_file = service.storage._artifacts_dir() / f"{artifacts[-1].artifact_id}.json"
                    if art_file.exists():
                        last_activity = max(last_activity, os.path.getmtime(art_file))
                
                created_dt = datetime.fromtimestamp(last_activity)
                delta_days = (today_date - created_dt.date()).days
                
                if delta_days == 0:
                    time_label = created_dt.strftime("%H:%M")
                    group = "today"
                elif delta_days == 1:
                    time_label = "1天前"
                    group = "yesterday"
                else:
                    time_label = f"{delta_days}天前"
                    group = "older"
                    
                sort_key = last_activity
            else:
                time_label = "刚刚"
                group = "today"
                sort_key = 0
                
            tasks_data.append((sort_key, task, time_label, group))
            
        # 按最后活跃时间倒序排列
        tasks_data.sort(key=lambda x: x[0], reverse=True)
        
        grouped = {"today": [], "yesterday": [], "older": []}
        for _, task, time_label, group in tasks_data:
            grouped[group].append({
                "id": task.task_id,
                "label": task.context.title,
                "time": time_label,
                "active": False
            })
        return grouped

    return app


def _normalize_create_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """标准化创建任务时的请求参数。

    过滤负面情绪，推导任务类型，并为不同类型的任务补充必要缺省字段。

    Args:
        payload (Dict[str, Any]): 原始输入参数负载。

    Returns:
        Dict[str, Any]: 标准化处理后的参数字典。
    """
    prompt = (payload.get("prompt") or payload.get("goal") or payload.get("business_goal") or "").strip()
    
    # 情绪拦截与提示词修饰调停
    from app.cli.utils import intercept_user_emotion
    new_prompt = intercept_user_emotion(prompt)
    if new_prompt != prompt:
        prompt = new_prompt
        if "prompt" in payload: payload["prompt"] = prompt
        elif "goal" in payload: payload["goal"] = prompt
        elif "business_goal" in payload: payload["business_goal"] = prompt

    # 推导或指定任务类型
    task_type = payload.get("type") or _infer_task_type(prompt)
    normalized = dict(payload)
    normalized["type"] = task_type
    normalized["username"] = payload.get("username") or "frontend"
    
    # 根据任务类型补齐特定字段
    if task_type == "acceptance_review":
        normalized["machine_spec"] = payload.get("machine_spec") or ""
        normalized["acceptance_protocol"] = payload.get("acceptance_protocol") or ""
        normalized["implementation_summary"] = payload.get("implementation_summary") or ""
        normalized["diff"] = payload.get("diff") or ""
        normalized.setdefault("title", payload.get("title") or _title_from_prompt(prompt, "Acceptance Review"))
    else:
        normalized["business_intent"] = (
            payload.get("business_intent")
            or payload.get("prompt")
            or payload.get("goal")
            or payload.get("business_goal")
            or ""
        )
        normalized.setdefault("title", payload.get("title") or _title_from_prompt(prompt, "Spec to Agent"))
    return normalized


def _infer_task_type(prompt: str) -> str:
    """根据输入提示词包含的关键词，智能推导任务类型。

    Args:
        prompt (str): 用户输入的提示文本。

    Returns:
        str: 识别出的任务类型，'spec_to_agent' 或 'acceptance_review'。
    """
    if any(keyword in prompt.lower() for keyword in ["review", "acceptance", "验收", "评审", "验收评审"]):
        return "acceptance_review"
    return "spec_to_agent"


def _title_from_prompt(prompt: str, fallback: str) -> str:
    """从原始提示文本中提取并清理出一段适合用作任务缩略标题的字符串。

    Args:
        prompt (str): 用户输入的提示文本。
        fallback (str): 提取失败时返回的备用标题。

    Returns:
        str: 清理裁剪后的 32 字符以内的标题。
    """
    clean = " ".join(prompt.split())
    if not clean:
        return fallback
    return clean[:32]


def _load_task_or_404(service: TaskService, task_id: str):
    """尝试加载指定任务，若任务不存在则抛出 FastAPI 404 HTTP 异常。

    Args:
        service (TaskService): 任务管理服务实例。
        task_id (str): 任务的唯一标识。

    Returns:
        Task: 加载成功的任务对象。

    Raises:
        HTTPException: 当找不到对应任务文件时抛出。
    """
    try:
        return service.get_task(task_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc


def _frontend_task(task: Any) -> Dict[str, Any]:
    """将后端的任务底层模型数据结构转换/转换为前端展示所需的 DTO 模型。

    Args:
        task (Any): 任务的底层模型实例。

    Returns:
        Dict[str, Any]: 适配前端视图展示的任务字典。
    """
    status_map = {"created": "pending", "running": "running", "waiting_for_user": "review", "completed": "done", "failed": "review", "blocked": "review", "cancelled": "done"}
    if task.definition.agents:
        agents = " + ".join(list(task.definition.agents.values()))
    else:
        if task.definition.type == "spec_to_agent":
            agents = "Compiler + Writer"
        elif task.definition.type == "acceptance_review":
            agents = "Reviewer + Writer"
        else:
            agents = "SYSTEM"
    knowledge_state = (getattr(task.context, "degradation_state", {}) or {}).get("knowledge", {})
    return {
        "id": task.task_id,
        "task_id": task.task_id,
        "title": task.context.title,
        "type": task.definition.type,
        "status": status_map.get(task.status.value, "pending"),
        "raw_status": task.status.value,
        "agent": agents,
        "priority": "medium",
        "updated": "刚刚",
        "waiting_step_id": task.waiting_step_id,
        "knowledge_status": {
            "state": "error" if knowledge_state.get("degraded") else ("ready" if knowledge_state.get("items", 0) > 0 else "no_results"),
            "degraded": bool(knowledge_state.get("degraded")),
            "error": knowledge_state.get("error"),
            "items": knowledge_state.get("items", 0),
            "preview": knowledge_state.get("preview", []),
        },
    }


def _event_to_frontend_message(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """将后端的结构化事件格式化映射为前端的对话气泡消息格式。

    过滤非前端展示事件，并提取消息块、裁决选项及 toast 异常反馈提示。

    Args:
        event (Dict[str, Any]): 原始结构化后端事件序列化字典。

    Returns:
        Optional[Dict[str, Any]]: 前端消息气泡模型；若不属于展示事件则返回 None。
    """
    role = event.get("role") or "SYSTEM"
    meta = AGENT_META.get(role, AGENT_META["SYSTEM"])
    event_type = event.get("type")
    payload = event.get("payload") or {}
    
    valid_frontend_events = {
        "workflow.step.started",
        "agent.message.chunk",
        "agent.message.completed",
        "arbitration.requested",
        "artifact.created",
        "task.completed",
        "task.cancelled",
        "task.failed",
        "tool.call.denied",
        "model.fallback",
    }
    
    if event_type not in valid_frontend_events:
        return None

    content = payload.get("summary")
    highlights = None
    step_id = payload.get("step_id") or event.get("id")
    
    if event_type == "workflow.step.started":
        if payload.get("step_type") != "agent":
            return None
        return {**meta, "id": step_id, "type": "typing", "content": "深度思考中...", "time": _format_event_time(event.get("created_at")), "created_at": event.get("created_at")}
    elif event_type == "agent.message.chunk":
        return {**meta, "id": step_id, "type": "chunk", "content": payload.get("chunk", ""), "time": _format_event_time(event.get("created_at")), "created_at": event.get("created_at")}
    elif event_type == "model.fallback":
        return {"id": event.get("id"), "type": "toast", "content": payload.get("message"), "time": _format_event_time(event.get("created_at")), "created_at": event.get("created_at")}
    elif event_type == "agent.message.completed":
        content = payload.get("content") or payload.get("summary") or "Agent 已完成本轮输出。"
    elif event_type == "arbitration.requested":
        dispute = payload.get("dispute_package", {})
        content = dispute.get("decision_needed") or "需要用户裁决后继续。"
        highlights = {"label": dispute.get("title", "需要裁决"), "color": meta["color"], "items": [item.get("pm_position") or item.get("label") for item in dispute.get("options", [])]}
    elif event_type == "artifact.created":
        content = f"文档产物已生成：{payload.get('name')}"
    elif event_type == "task.completed":
        content = "任务已完成，最终 Markdown 文档已准备好。"
    elif event_type == "task.cancelled":
        content = "任务已暂停/取消。"
    elif event_type == "task.failed":
        content = "任务执行失败。"
    elif event_type == "tool.call.denied":
        content = payload.get("summary") or f"工具调用被拒绝：{payload.get('tool_name')}"
        
    if not content and event_type != "model.fallback":
        return None
    return {**meta, "id": step_id, "content": content, "highlights": highlights, "isFinal": event_type == "task.completed", "time": _format_event_time(event.get("created_at")), "created_at": event.get("created_at")}


def _format_event_time(value: Optional[str]) -> str:
    """从 ISO-8601 事件时间字符串中提取出简短的时间表示（如 HH:MM）。

    Args:
        value (Optional[str]): 原始 ISO 时间字符串。

    Returns:
        str: 裁剪后的时间字符串，默认为 '刚刚'。
    """
    if not value or "T" not in value:
        return "刚刚"
    return value.split("T", 1)[1][:5]


def _knowledge_items() -> List[Dict[str, Any]]:
    """生成预置的 Mock 知识库检索条目，用于前端静态数据备用演示。

    Returns:
        List[Dict[str, Any]]: Mock 知识库条目列表。
    """
    return [
        {"id": "kb_001", "type": "doc", "title": "EvoCanvas 协作与编译协议", "desc": "TaskDefinition、WorkflowEngine、ToolService 与结构化事件协议。", "tags": ["架构", "后端"], "updated": "刚刚", "author": "Codex"},
        {"id": "kb_002", "type": "rule", "title": "Agent 必须通过 ToolPolicy 调用能力", "desc": "禁止 Agent 绕过受控工具边界，避免把未经授权的数据静默写成结论。", "tags": ["规则", "安全"], "updated": "刚刚", "author": "Reviewer"},
        {"id": "kb_003", "type": "template", "title": "结构化交接物标准模板", "desc": "用于沉淀问题、待澄清、约束与待决策的结构化交接模版。", "tags": ["模板", "交接物"], "updated": "刚刚", "author": "Canvas AI"},
    ]


def _build_source_ref_summary(
    connector_type: str,
    display_name: str,
    query_text: Optional[str],
    metric_name: Optional[str],
    filters: Dict[str, Any],
) -> str:
    """为外部数据引用生成可审计、可被 AI 消费的快照摘要。"""

    parts = [f"数据引用 {display_name} 已生成只读快照。"]
    if connector_type == "dashboard_metric" and metric_name:
        parts.append(f"当前关注指标为 {metric_name}。")
    elif query_text:
        parts.append(f"查询说明：{query_text[:160]}。")
    if filters:
        filter_text = "、".join(f"{key}={value}" for key, value in filters.items())
        parts.append(f"过滤条件：{filter_text}。")
    parts.append("该引用会作为结构化证据参与输入编译，而不会自动写入知识库。")
    return "".join(parts)


def _rule_items() -> List[Dict[str, Any]]:
    """生成预置的 Mock 可信规则条目，用于前端静态数据演示。

    Returns:
        List[Dict[str, Any]]: Mock 可信规则条目列表。
    """
    return [
        {"id": "R-0021", "title": "技术方案必须包含熔断降级策略", "desc": "Diff Agent 候选法则示例，等待人工批准后才能入可信区。", "source": "PRD 最小工作流", "sourceId": "task_demo", "extractedAt": "刚刚", "confidence": 94, "status": "pending"},
        {"id": "R-0017", "title": "文档标题需包含版本号", "source": "历史任务", "approvedAt": "3 天前", "confidence": 88, "status": "approved"},
        {"id": "R-0015", "title": "所有任务默认启用深度思考模式", "source": "历史任务", "rejectedAt": "1 周前", "confidence": 60, "status": "rejected"},
    ]


def _recycle_items() -> List[Dict[str, Any]]:
    """生成预置的 Mock 回收站已被删除文档条目，用于静态数据演示。

    Returns:
        List[Dict[str, Any]]: Mock 回收站已删除条目列表。
    """
    return [
        {"id": "trash_001", "name": "旧版产品需求文档 v1.0.md", "type": "doc", "size": "32 KB", "deletedAt": "今天", "deletedBy": "PM Agent"},
    ]


# 自动初始化实例化 FastAPI app 全局单例
app = create_app() if FastAPI is not None else None
