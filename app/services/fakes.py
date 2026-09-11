"""Phase 1 测试与本地契约演示中使用的 Mock 服务层实现。

本模块提供了一些轻量级、不依赖外部服务（如真实 LLM、数据库等）的伪实现（Fakes），
用于快速运行单元测试、验证核心流程接口契约。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.artifacts import Artifact
from app.core.context import TaskContext
from app.core.events import Event, EventBus
from app.core.ports import LLMResult
from app.core.task import Task, TaskDefinition

class FakeLLM:
    """供单元测试使用的模拟大语言模型（LLM）服务。

    通过硬编码回复与简单的字符串拼接来模拟 LLM 对不同角色的响应，支持同步请求与流式生成器。
    """

    def invoke(self, role: str, prompt: str, context: Dict[str, Any]) -> LLMResult:
        """模拟同步非流式 LLM 调用。

        如果角色是 "Reviewer"，返回固定结果 "PASS"；
        否则，根据上下文中的任务标题、业务目标拼接响应字符串。

        Args:
            role: 执行任务的代理角色。
            prompt: 用户的提示词。
            context: 任务关联的上下文环境。

        Returns:
            LLMResult: 模拟的 LLM 响应结果。
        """
        if "Evaluate Requirement Coverage" in prompt:
            req_ids = context.get("req_ids") or ["req_default"]
            payload = {
                req_id: {"covered": True, "notes": "Verified by FakeLLM", "evidence_refs": []}
                for req_id in req_ids
            }
            return LLMResult(content=json.dumps(payload), structured=payload)
        if "Output JSON: {\"issues\": [], \"fix_tasks\": []}" in prompt:
            payload = {"issues": [], "fix_tasks": []}
            return LLMResult(content=json.dumps(payload), structured=payload)
        if "structural AST" in prompt and "primary_requirement" in prompt:
            requirement = context.get("pre_compiled_data", "").splitlines()[0].replace("INTENT:", "").strip()
            payload = {
                "primary_requirement": requirement or "未命名任务",
                "dependencies": ["system"],
                "strict_contracts": ["编译结果必须可追溯到原始意图"],
                "environment": {"os_target": "linux", "node_version": "20.x"},
                "security": {"require_auth": True},
            }
            return LLMResult(content=json.dumps(payload, ensure_ascii=False), structured=payload)
        if "OpenQuestionIdentifier" in prompt and "has_questions" in prompt:
            payload = {"has_questions": False, "questions": [], "diagnostic_matrix_runs": 1}
            return LLMResult(content=json.dumps(payload, ensure_ascii=False), structured=payload)
        if "select the most appropriate peer AI technical colleague" in prompt:
            payload = {"peer_target": "codex"}
            return LLMResult(content=json.dumps(payload), structured=payload)
        if "Generate Behavior-Driven Development" in prompt:
            payload = {"test_vectors": ["Given the compiled requirement, When implementation is reviewed, Then acceptance criteria are satisfied"]}
            return LLMResult(content=json.dumps(payload), structured=payload)
        if role == "Reviewer":
            return LLMResult(content="PASS", structured={"role": role})
        title = context.get("title") or context.get("feature") or context.get("module_name") or "未命名任务"
        goal = context.get("goal") or context.get("business_goal") or ""
        content = f"{role} response for {title}: {goal}"
        return LLMResult(content=content, structured={"role": role, "title": title, "goal": goal})

    def invoke_stream(self, role: str, prompt: str, context: Dict[str, Any]):
        """模拟流式 LLM 调用，逐步产出字符。

        Args:
            role: 执行任务的代理角色。
            prompt: 用户的提示词。
            context: 任务关联的上下文环境。

        Yields:
            str: 逐字产出的响应 Token 片段。
        """
        title = context.get("title") or context.get("feature") or context.get("module_name") or "未命名任务"
        goal = context.get("goal") or context.get("business_goal") or ""
        content = f"{role} response for {title}: {goal}"
        
        # 逐字生成，模拟打字机流式效果
        for char in content:
            yield char

class FakeKnowledge:
    """供单元测试使用的模拟知识检索库。

    不执行真实的向量检索，直接返回固定的本地知识快照结构。
    """

    def retrieve(self, query: str, scope: Optional[str] = None) -> Dict[str, Any]:
        """模拟知识检索逻辑，返回固定的 mock 数据。

        Args:
            query: 检索的关键词或查询语句。
            scope: 检索范围。

        Returns:
            Dict[str, Any]: 模拟的检索结果字典。
        """
        return {
            "query": query,
            "scope": scope or "default",
            "items": [
                {"title": "本地知识快照", "summary": f"与 {query} 相关的占位知识。"},
            ],
            "degraded": False,
        }

import re


def _safe_id(value: str) -> str:
    """严格校验标识符格式，防范路径穿越与非法字符注入。"""
    if not value or not re.match(r"^[a-zA-Z0-9_-]+$", str(value)):
        raise ValueError(f"invalid identifier: {value!r}")
    return str(value)


class FakeStorage:
    """基于文件系统的本地伪存储实现类。

    使用 JSON 和 JSONL 格式在指定的本地目录下读写 Task、Context、Event 审计记录与 Artifact 产物。
    主要用于开发环境 and Phase 1 单元测试。
    """

    def __init__(self, root: Path, event_bus: Optional[EventBus] = None):
        """初始化 FakeStorage 实例。

        Args:
            root: 文件存储的根路径。
            event_bus: 可选的事件总线，用于实时发布存储引起的审计事件。
        """
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.event_bus = event_bus

    def _task_dir(self, task_id: str) -> Path:
        """根据任务 ID 获取并创建对应的物理存储目录。

        Args:
            task_id: 任务的唯一标识符。

        Returns:
            Path: 任务存储的 Path 对象。
        """
        safe_task_id = _safe_id(task_id)
        path = self.root / "tasks" / safe_task_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _artifacts_dir(self) -> Path:
        """获取并创建统一的产物（Artifacts）存储目录。

        Returns:
            Path: 产物存储的 Path 对象。
        """
        path = self.root / "artifacts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def canvas_root(self) -> Path:
        """获取并创建 EvoCanvas 工作区数据的根目录。

        当前首版将画布数据统一放在 `canvas/` 命名空间下，
        供工作区根对象等 EvoCanvas 原生结构直接复用。
        """
        path = self.root / "canvas"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_task(self, task: Task) -> None:
        """持久化任务的元数据及状态到 task.json 文件。

        Args:
            task: 待持久化的任务对象。
        """
        self._task_dir(task.task_id).joinpath("task.json").write_text(
            json.dumps(task.to_record(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def delete_task_directory(self, task_id: str) -> None:
        """清理删除指定任务的所有本地物理文件目录。

        Args:
            task_id: 待清理的任务 ID。
        """
        import shutil
        path = self._task_dir(task_id)
        if path.exists():
            shutil.rmtree(path)

    def load_task(self, task_id: str, registry: Dict[str, TaskDefinition]) -> Task:
        """从本地磁盘加载指定 ID 的任务实体及上下文。

        Args:
            task_id: 任务的唯一标识符。
            registry: 支持的任务定义注册表。

        Returns:
            Task: 重构恢复后的 Task 实体。
        """
        data = json.loads(self._task_dir(task_id).joinpath("task.json").read_text(encoding="utf-8"))
        context = self.load_context(task_id)
        return Task.from_record(registry[data["task_type"]], context, data)

    def list_tasks(self, registry: Dict[str, TaskDefinition]) -> List[Task]:
        """列出存储根目录下所有已持久化的任务，按修改时间逆序排序。

        Args:
            registry: 支持的任务定义注册表。

        Returns:
            List[Task]: 已保存的任务列表。
        """
        tasks_dir = self.root / "tasks"
        if not tasks_dir.exists():
            return []
        tasks = []
        for path in sorted(tasks_dir.glob("task_*/task.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                tasks.append(self.load_task(path.parent.name, registry))
            except Exception:
                pass
        return tasks

    def save_context(self, context: TaskContext) -> None:
        """持久化任务上下文数据到 context.json。

        Args:
            context: 待持久化的上下文实体。
        """
        self._task_dir(context.task_id).joinpath("context.json").write_text(
            json.dumps(context.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_context(self, task_id: str) -> TaskContext:
        """加载指定任务的上下文实体。

        Args:
            task_id: 任务 ID。

        Returns:
            TaskContext: 恢复出来的上下文对象。
        """
        data = json.loads(self._task_dir(task_id).joinpath("context.json").read_text(encoding="utf-8"))
        return TaskContext.from_dict(data)

    def append_event(self, event: Event) -> Event:
        """将事件追加持久化到本地 events.jsonl 中，并触发 EventBus 发布。

        流式输出分片事件（agent.message.chunk）为了性能不单独落盘，直接在总线上推送。

        Args:
            event: 待追加并发布的结构化事件。

        Returns:
            Event: 追加/更新了 ID 后的事件实体。
        """
        if event.type != "agent.message.chunk":
            events = self.read_events(event.task_id)
            if not event.id:
                event.id = f"evt_{len(events) + 1:06d}"
            with self._task_dir(event.task_id).joinpath("events.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        else:
            if not event.id:
                import time
                event.id = f"chunk_{int(time.time()*1000)}"
                
        if self.event_bus:
            self.event_bus.publish(event)
        return event

    def read_events(self, task_id: str) -> List[Event]:
        """从 events.jsonl 读取指定任务的所有审计事件历史。

        Args:
            task_id: 任务 ID。

        Returns:
            List[Event]: 历史审计事件列表。
        """
        path = self._task_dir(task_id) / "events.jsonl"
        if not path.exists():
            return []
        events = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(Event.from_dict(json.loads(line)))
        return events

    def save_checkpoint(self, task: Task, last_completed_step_id: str, next_step_id: Optional[str]) -> None:
        """保存任务的执行检查点（Checkpoint）。

        Args:
            task: 当前执行的任务实体。
            last_completed_step_id: 上一个成功执行完毕的步骤 ID。
            next_step_id: 即将执行的下一个步骤 ID。
        """
        self._task_dir(task.task_id).joinpath("checkpoint.json").write_text(
            json.dumps(
                {
                    "task_id": task.task_id,
                    "last_completed_step_id": last_completed_step_id,
                    "next_step_id": next_step_id,
                    "status": task.status.value,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def load_checkpoint(self, task_id: str) -> Dict[str, Any]:
        """读取指定任务的检查点信息。

        Args:
            task_id: 任务 ID。

        Returns:
            Dict[str, Any]: 包含 checkpoint 详细键值对的字典，若不存在返回空字典。
        """
        path = self._task_dir(task_id) / "checkpoint.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def write_artifact(self, task_id: str, name: str, content: str, created_by: str = "Writer") -> Artifact:
        """写入/注册一个新的产物（Artifact）并持久化到本地。

        Args:
            task_id: 产物关联的任务 ID。
            name: 产物名称（文件名）。
            content: 产物的文本内容。
            created_by: 创建产物的角色，默认为 "Writer"。

        Returns:
            Artifact: 成功写入的产物实体。
        """
        for artifact in self.list_artifacts(task_id):
            if artifact.name == name:
                return artifact
        artifact_id = f"artifact_{task_id}_{len(self.list_artifacts(task_id)) + 1:03d}"
        artifact = Artifact(
            artifact_id=artifact_id,
            task_id=task_id,
            name=name,
            version=1,
            created_by=created_by,
            summary=f"Generated {name}",
            content=content,
        )
        self._artifacts_dir().joinpath(f"{artifact_id}.json").write_text(
            json.dumps(artifact.to_dict(include_content=True), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return artifact

    def update_artifact(self, artifact_id: str, content: str, updated_by: str = "user") -> Artifact:
        """更新已存在产物的内容，并增加版本号。

        如果新内容与老内容完全相同，则跳过更新，直接返回当前版本。

        Args:
            artifact_id: 产物唯一标识符。
            content: 新的产物内容。
            updated_by: 更新发起者，默认为 "user"。

        Returns:
            Artifact: 更新后的产物实体。
        """
        safe_id = _safe_id(artifact_id)
        current = self.read_artifact(safe_id)
        if (current.content or "").strip() == (content or "").strip():
            return current
        updated = Artifact(
            artifact_id=safe_id,
            task_id=current.task_id,
            name=current.name,
            version=current.version + 1,
            content_type=current.content_type,
            created_by=updated_by,
            summary=f"Updated {current.name}",
            content=content,
        )
        self._artifacts_dir().joinpath(f"{safe_id}.json").write_text(
            json.dumps(updated.to_dict(include_content=True), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return updated

    def list_artifacts(self, task_id: str) -> List[Artifact]:
        """列出指定任务产生的所有产物（Artifacts）。

        Args:
            task_id: 任务 ID。

        Returns:
            List[Artifact]: 产物实体列表。
        """
        safe_task_id = _safe_id(task_id)
        artifacts = []
        for path in sorted(self._artifacts_dir().glob("artifact_*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("task_id") == safe_task_id:
                artifacts.append(Artifact.from_dict(data))
        return artifacts

    def read_artifact(self, artifact_id: str) -> Artifact:
        """读取指定产物的详细内容及元数据。

        Args:
            artifact_id: 产物的唯一标识。

        Returns:
            Artifact: 产物对象。
        """
        safe_id = _safe_id(artifact_id)
        path = self._artifacts_dir() / f"{safe_id}.json"
        return Artifact.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def backup_artifact(self, artifact_id: str) -> Dict[str, Any]:
        """为指定产物创建备份文件，并记录备份标识符。

        备份文件将以 backup_{artifact_id}_v{version}.json 的格式保存在产物目录下。

        Args:
            artifact_id: 产物的唯一标识。

        Returns:
            Dict[str, Any]: 包含 backup_id 的元数据。
        """
        safe_id = _safe_id(artifact_id)
        artifact = self.read_artifact(safe_id)
        backup_id = f"backup_{safe_id}_v{artifact.version}"
        backup_path = self._artifacts_dir() / f"{backup_id}.json"
        backup_path.write_text(json.dumps(artifact.to_dict(include_content=True), ensure_ascii=False, indent=2), encoding="utf-8")
        return {"backup_id": backup_id}
