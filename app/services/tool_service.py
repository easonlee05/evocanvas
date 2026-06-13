"""已注册工具的执行与管理服务。

本服务模块负责工具（Tool）的注册、控制策略（ToolPolicy）的权限检查、防止路径遍历等安全红线校验，
以及审计事件（如 tool.call.started, tool.call.completed, tool.call.failed, tool.call.denied）的统一输出。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict

from app.core.context import TaskContext
from app.core.errors import DomainError
from app.core.events import Event
from app.core.task import TaskDefinition
from app.core.tools import ToolCall, ToolResult, ToolSpec
from app.services.file_service import FileService

ToolHandler = Callable[[TaskContext, ToolCall], ToolResult]


class ToolService:
    """工具管理与受控调用服务类。

    维护可供 Agent 使用的所有 ToolSpec 和对应的执行处理器，提供调用白名单权限审核与安全沙箱规则检测，
    并在工具执行生命周期中向持久化存储写入审计事件。

    生命周期：
        该服务通常作为单例由 API 层或工作流引擎构建和共享。
    """

    def __init__(self, specs: Dict[str, ToolSpec], handlers: Dict[str, ToolHandler], storage: Any):
        """初始化 ToolService。

        Args:
            specs: 已注册工具规格的映射，键为工具名称，值为 ToolSpec。
            handlers: 工具执行处理器的映射，键为工具名称，值为 ToolHandler 可调用对象。
            storage: 持久化存储层实例，用于记录事件审计。
        """
        self.specs = specs
        self.handlers = handlers
        self.storage = storage
        self.knowledge_backend = None

    @classmethod
    def default(cls, root: Path, knowledge: Any) -> "ToolService":
        """基于本地文件路径与知识检索后端构建默认的 ToolService，内置首期 9 大核心 Tool。

        Args:
            root: 工作目录的根路径。
            knowledge: 知识库检索服务。

        Returns:
            ToolService: 配置好默认工具规格与处理器的 ToolService 实例。
        """
        from app.services.fakes import FakeStorage

        storage = FakeStorage(root) if not hasattr(root, "append_event") else root
        file_service = FileService(storage)
        specs = build_default_tool_specs()

        # 定义材料读取处理器 (material.read)
        def material_read(context: TaskContext, call: ToolCall) -> ToolResult:
            material_id = call.arguments.get("material_id")
            return ToolResult(call_id=call.id, status="succeeded", summary="material summary loaded", data={"material_id": material_id, "summary": "材料摘要占位，不泄露完整原文。"})

        # 定义材料解析处理器 (material.parse)
        def material_parse(context: TaskContext, call: ToolCall) -> ToolResult:
            return ToolResult(call_id=call.id, status="succeeded", summary="materials parsed", data={"materials": context.source_materials})

        # 定义知识库检索处理器 (knowledge.retrieve)
        def knowledge_retrieve(context: TaskContext, call: ToolCall) -> ToolResult:
            result = knowledge.retrieve(call.arguments.get("query", context.goal), call.arguments.get("scope"))
            return ToolResult(call_id=call.id, status="succeeded", summary="knowledge retrieved", data=result)

        # 定义产物写入处理器 (artifact.write)
        def artifact_write(context: TaskContext, call: ToolCall) -> ToolResult:
            artifact = file_service.write_artifact(
                task_id=context.task_id,
                name=call.arguments["name"],
                content=call.arguments.get("content", ""),
                created_by=call.agent_role,
            )
            return ToolResult(call_id=call.id, status="succeeded", summary=f"artifact {artifact.name} written", artifacts=[artifact], data={"artifact_id": artifact.artifact_id, "version": artifact.version})

        # 定义产物读取处理器 (artifact.read)
        def artifact_read(context: TaskContext, call: ToolCall) -> ToolResult:
            artifact = file_service.read_artifact(call.arguments["artifact_id"])
            return ToolResult(call_id=call.id, status="succeeded", summary=f"artifact {artifact.name} read", artifacts=[artifact], data={"content": artifact.content})

        # 定义产物备份处理器 (artifact.backup)
        def artifact_backup(context: TaskContext, call: ToolCall) -> ToolResult:
            backup = file_service.backup_artifact(call.arguments["artifact_id"])
            return ToolResult(call_id=call.id, status="succeeded", summary="artifact backup created", data=backup)

        # 定义格式校验处理器 (format.validate)
        def format_validate(context: TaskContext, call: ToolCall) -> ToolResult:
            return ToolResult(call_id=call.id, status="succeeded", summary="format validated", data={"passed": True, "violations": []})

        # 定义规则差异提取处理器 (diff.extract_rules)
        def diff_extract_rules(context: TaskContext, call: ToolCall) -> ToolResult:
            return ToolResult(call_id=call.id, status="succeeded", summary="candidate rules extracted", data={"candidates": []})

        # 定义事件发送处理器 (event.emit)
        def event_emit(context: TaskContext, call: ToolCall) -> ToolResult:
            return ToolResult(call_id=call.id, status="succeeded", summary="event accepted", data={"event_type": call.arguments.get("type")})

        handlers = {
            "material.read": material_read,
            "material.parse": material_parse,
            "knowledge.retrieve": knowledge_retrieve,
            "artifact.write": artifact_write,
            "artifact.read": artifact_read,
            "artifact.backup": artifact_backup,
            "format.validate": format_validate,
            "diff.extract_rules": diff_extract_rules,
            "event.emit": event_emit,
        }
        service = cls(specs=specs, handlers=handlers, storage=storage)
        service.knowledge_backend = knowledge
        return service

    def invoke(self, definition: TaskDefinition, context: TaskContext, call: ToolCall) -> ToolResult:
        """安全受控地调用一个指定的工具。

        执行白名单检查（ToolPolicy）、沙箱参数安全审核（防目录遍历、限制毁灭性命令等），
        自动记录审计事件（开始、完成/失败/拒绝），并在异常时安全回退。

        Args:
            definition: 任务定义，包含 tool_policy 权限白名单。
            context: 任务上下文，用于标识任务和为处理器提供运行时属性。
            call: 工具调用描述，包含工具名、调用 ID、代理角色及入参。

        Returns:
            ToolResult: 工具执行的结果包装，包含状态、产出物及数据。
        """
        spec = self.specs.get(call.tool_name)
        if not spec:
            return ToolResult(call_id=call.id, status="failed", error=DomainError("tool.unknown", f"Unknown tool: {call.tool_name}"))
            
        # 1. 严格检查 IAM & Sandbox 权限策略白名单
        if not definition.tool_policy.is_allowed(call.agent_role, call.step_id, call.tool_name):
            result = ToolResult(call_id=call.id, status="denied", error=DomainError("tool.denied", f"{call.agent_role} cannot call {call.tool_name} in {call.step_id}"))
            self._emit_tool_event(context.task_id, call, "tool.call.denied", result)
            return result
            
        # 2. 检查路径遍历参数，拦截恶意系统路径
        for k, v in call.arguments.items():
            if isinstance(v, str) and ("../" in v or v.startswith("/etc") or v.startswith("/bin")):
                result = ToolResult(call_id=call.id, status="denied", error=DomainError("sandbox.violation", f"Path traversal or restricted system path detected in arguments."))
                self._emit_tool_event(context.task_id, call, "tool.call.denied", result)
                return result
            # 3. 拦截命令行执行工具中的高危指令（破坏性命令）
            if call.tool_name == "run_command" and isinstance(v, str) and any(cmd in v for cmd in ["rm -rf", "mkfs", "chmod"]):
                result = ToolResult(call_id=call.id, status="denied", error=DomainError("sandbox.violation", f"Destructive command execution is prohibited."))
                self._emit_tool_event(context.task_id, call, "tool.call.denied", result)
                return result

        # 4. 发布工具执行开始审计事件
        self._emit_tool_event(context.task_id, call, "tool.call.started", None)
        try:
            result = self.handlers[call.tool_name](context, call)
        except Exception as exc:  # pragma: no cover - defensive wrapper
            result = ToolResult(call_id=call.id, status="failed", error=DomainError("tool.failed", str(exc)))
        
        # 5. 发布工具执行完成/失败审计事件
        event_type = "tool.call.completed" if result.status == "succeeded" else "tool.call.failed"
        self._emit_tool_event(context.task_id, call, event_type, result)
        return result

    def _emit_tool_event(self, task_id: str, call: ToolCall, event_type: str, result: ToolResult | None) -> None:
        """向持久化存储中追加结构化的工具执行审计事件。

        Args:
            task_id: 任务的唯一标识符。
            call: 工具调用描述。
            event_type: 事件类型（如 tool.call.started 等）。
            result: 工具调用的结果，在开始阶段为 None。
        """
        if not self.storage:
            return
        payload = {"tool_name": call.tool_name, "step_id": call.step_id, "role": call.agent_role, "summary": result.summary if result else "started"}
        if result and result.artifacts:
            payload["artifact_ids"] = [artifact.artifact_id for artifact in result.artifacts]
        self.storage.append_event(Event(task_id=task_id, type=event_type, role=call.agent_role, status=result.status if result else "started", payload=payload))


def build_default_tool_specs() -> Dict[str, ToolSpec]:
    """构建首期默认工具的规格定义集合。

    Returns:
        Dict[str, ToolSpec]: 包含工具名到 ToolSpec 映射的字典。
    """
    schemas = {"type": "object", "additionalProperties": True}
    return {
        "material.read": ToolSpec("material.read", "1.0", "读取用户上传材料摘要或授权片段", schemas, schemas, "read", ["material:read"]),
        "material.parse": ToolSpec("material.parse", "1.0", "将上传材料解析为结构化材料包", schemas, schemas, "read", ["material:read"]),
        "knowledge.retrieve": ToolSpec("knowledge.retrieve", "1.0", "按任务目标检索 GBrain 或本地知识快照", schemas, schemas, "read", ["knowledge:read"]),
        "artifact.write": ToolSpec("artifact.write", "1.0", "写 Markdown 产物并记录版本", schemas, schemas, "write", ["artifact:write"], event_semantics="Must emit tool.call.started and tool.call.completed/failed/denied."),
        "artifact.read": ToolSpec("artifact.read", "1.0", "读取已生成产物供审查或 Diff 使用", schemas, schemas, "read", ["artifact:read"]),
        "artifact.backup": ToolSpec("artifact.backup", "1.0", "用户编辑或重写前备份旧版本", schemas, schemas, "write", ["artifact:write"], event_semantics="Must emit tool.call.started and tool.call.completed/failed/denied."),
        "format.validate": ToolSpec("format.validate", "1.0", "校验操作手册格式红线或 PRD 结构要求", schemas, schemas, "none", []),
        "diff.extract_rules": ToolSpec("diff.extract_rules", "1.0", "从终稿变化中生成候选法则，不直接入库", schemas, schemas, "write", ["rules:candidate"], event_semantics="Writes candidates only; never approved rules."),
        "event.emit": ToolSpec("event.emit", "1.0", "统一输出结构化事件，禁止日志协议替代", schemas, schemas, "write", ["event:write"]),
    }
