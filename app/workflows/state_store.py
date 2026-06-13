"""工作流运行与检查点历史存储，以及回滚规划器。

该模块提供了一种基于内存账本的工作流状态存储，支持从事件溯源（Event Sourcing）的角度
还原工作流的运行历史与检查点，并能根据状态变化规划当某个步骤失败时的回滚策略。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class WorkflowRollbackPlan:
    """表示工作流回滚方案的数据类。

    该类记录了在步骤失败时，工作流引擎应回滚到哪个已完成的检查点，
    并指明废弃哪些已污染/未成功提交的步骤，以及如何恢复执行。
    """

    task_id: str
    failed_step_id: str
    rollback_to_step_id: Optional[str]
    resume_step_id: Optional[str]
    discarded_step_ids: List[str]
    checkpoint: Optional[Dict[str, Any]] = None


@dataclass
class WorkflowStateStore:
    """基于内存的事件源式工作流状态账本。

    该类通过接收和记录工作流事件，在内存中动态维护运行状态记录（Runs）与检查点记录（Checkpoints）。
    """

    runs_by_task: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    checkpoints_by_task: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    def record_run_started(self, task_id: str, run_id: str, *, start_step_id: Optional[str] = None) -> Dict[str, Any]:
        """记录任务的运行生命周期开始事件。

        Args:
            task_id (str): 任务的唯一标识。
            run_id (str): 运行周期的唯一标识。
            start_step_id (Optional[str], optional): 从哪个步骤启动。默认为 None。

        Returns:
            Dict[str, Any]: 写入账本的运行开始条目字典。
        """
        entry = {"event": "run.started", "task_id": task_id, "run_id": run_id, "start_step_id": start_step_id}
        self.runs_by_task.setdefault(task_id, []).append(entry)
        return entry

    def record_run_finished(self, task_id: str, run_id: str, *, status: str) -> Dict[str, Any]:
        """记录任务的运行生命周期结束事件。

        Args:
            task_id (str): 任务的唯一标识。
            run_id (str): 运行周期的唯一标识。
            status (str): 运行结束时的最终状态（如 completed、failed 等）。

        Returns:
            Dict[str, Any]: 写入账本的运行结束条目字典。
        """
        entry = {"event": "run.finished", "task_id": task_id, "run_id": run_id, "status": status}
        self.runs_by_task.setdefault(task_id, []).append(entry)
        return entry

    def record_checkpoint(self, task_id: str, checkpoint: Dict[str, Any]) -> Dict[str, Any]:
        """记录并存储一个新的任务检查点快照。

        Args:
            task_id (str): 任务的唯一标识。
            checkpoint (Dict[str, Any]): 包含当前检查点各种运行时属性的字典。

        Returns:
            Dict[str, Any]: 写入账本的检查点条目字典。
        """
        entry = dict(checkpoint)
        entry.setdefault("task_id", task_id)
        self.checkpoints_by_task.setdefault(task_id, []).append(entry)
        return entry

    def run_history(self, task_id: str) -> List[Dict[str, Any]]:
        """获取指定任务的运行历史事件条目列表。

        Args:
            task_id (str): 任务的唯一标识。

        Returns:
            List[Dict[str, Any]]: 任务的运行启动/结束事件条目拷贝。
        """
        return list(self.runs_by_task.get(task_id, []))

    def checkpoint_history(self, task_id: str) -> List[Dict[str, Any]]:
        """获取指定任务的所有历史检查点列表。

        Args:
            task_id (str): 任务的唯一标识。

        Returns:
            List[Dict[str, Any]]: 任务的历史检查点列表拷贝。
        """
        return list(self.checkpoints_by_task.get(task_id, []))

    def latest_checkpoint(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取指定任务最近一次存储的检查点。

        Args:
            task_id (str): 任务的唯一标识。

        Returns:
            Optional[Dict[str, Any]]: 最近一个检查点条目；若不存在则返回 None。
        """
        history = self.checkpoint_history(task_id)
        return history[-1] if history else None

    @classmethod
    def from_events(cls, task_id: str, events: Iterable[Any]) -> "WorkflowStateStore":
        """从历史事件流（Event Stream）中动态还原构建一个完整的 `WorkflowStateStore` 状态实例。

        该方法主要用于系统崩溃或重启后，基于持久化的事件回溯整个工作流的状态轨迹。

        Args:
            task_id (str): 任务的唯一标识。
            events (Iterable[Any]): 相关的结构化或字典类型的事件序列。

        Returns:
            WorkflowStateStore: 基于事件回演重建的状态账本实例。
        """
        store = cls()
        for event in events:
            event_type, payload = cls._event_parts(event)
            # 处理工作流启动事件
            if event_type == "workflow.run.started":
                store.record_run_started(task_id, str(payload.get("run_id", "")), start_step_id=payload.get("start_step_id"))
            # 处理工作流运行完成事件
            elif event_type == "workflow.run.completed":
                store.record_run_finished(
                    task_id,
                    str(payload.get("run_id", "")),
                    status=str(payload.get("task_status") or payload.get("status") or "completed")
                )
            # 每一个成功的步骤对应一次临时的检查点保存
            elif event_type == "workflow.step.completed":
                step_id = payload.get("step_id")
                if step_id:
                    store.record_checkpoint(
                        task_id,
                        {
                            "run_id": payload.get("run_id"),
                            "last_completed_step_id": step_id,
                            "next_step_id": payload.get("next_step_id"),
                            "status": "running",
                        },
                    )
        return store

    @staticmethod
    def _event_parts(event: Any) -> tuple[str, Dict[str, Any]]:
        """从事件对象或字典中提取事件类型和载荷字典。

        Args:
            event (Any): 事件结构。

        Returns:
            tuple[str, Dict[str, Any]]: (事件类型, 事件载荷字典) 的二元组。
        """
        if isinstance(event, dict):
            return str(event.get("type", "")), dict(event.get("payload", {}))
        return str(getattr(event, "type", "")), dict(getattr(event, "payload", {}) or {})


@dataclass
class WorkflowRollbackPlanner:
    """分析工作流状态账本并生成回滚方案的规划器。"""

    state_store: WorkflowStateStore

    def plan_rollback(self, task_id: str, *, failed_step_id: str) -> WorkflowRollbackPlan:
        """为失败的步骤制定回滚方案。

        它查找最后一个成功提交的检查点步骤，作为回滚目标。并将失败的步骤标记为需要废弃。

        Args:
            task_id (str): 任务的唯一标识。
            failed_step_id (str): 发生失败的步骤 ID。

        Returns:
            WorkflowRollbackPlan: 计算出的具体回滚方案。
        """
        history = self.state_store.checkpoint_history(task_id)
        # 获取最近一次成功的步骤对应的检查点
        checkpoint = history[-1] if history else None
        # 如果存在，则回滚目标为该检查点的 last_completed_step_id，否则回退到最初
        rollback_to = checkpoint.get("last_completed_step_id") if checkpoint else None
        # 恢复点为检查点的 next_step_id，否则默认在失败步骤重试
        resume = checkpoint.get("next_step_id") if checkpoint else failed_step_id
        
        return WorkflowRollbackPlan(
            task_id=task_id,
            failed_step_id=failed_step_id,
            rollback_to_step_id=rollback_to,
            resume_step_id=resume,
            discarded_step_ids=[failed_step_id],
            checkpoint=checkpoint,
        )

