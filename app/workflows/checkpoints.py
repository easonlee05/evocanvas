"""包含存储兼容能力的工作流检查点助手模块。

该模块提供了在工作流执行中构建、恢复和持久化检查点（Checkpoint）的核心工具类。
通过检查点机制，系统能够在任务中断、崩溃或需要用户人工介入后，准确地从最近的有效状态进行恢复和重试。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from app.core.task import Task, TaskStatus


@dataclass
class CheckpointManager:
    """管理事务风格检查点载荷的构建与持久化。

    该类通过代理底层存储引擎，支持在不修改既有表结构的情况下，记录和存储任务的详细执行轨迹。
    """

    storage: Any

    def resume_step_id(self, checkpoint: Dict[str, Any]) -> Optional[str]:
        """根据检查点信息决定应当恢复执行的下一步骤 ID。

        如果检查点状态为等待用户决策，则不需要自动恢复下一步，返回 None。

        Args:
            checkpoint (Dict[str, Any]): 检查点数据字典。

        Returns:
            Optional[str]: 待恢复的下一步骤 ID；若无需恢复，则返回 None。
        """
        # 如果当前任务处于等待用户交互的状态，则不返回自动恢复的步骤 ID
        if checkpoint.get("status") == TaskStatus.WAITING_FOR_USER.value:
            return None
        next_step_id = checkpoint.get("next_step_id")
        return str(next_step_id) if next_step_id else None

    def build_payload(
        self,
        *,
        task_id: str,
        run_id: str,
        last_completed_step_id: str,
        next_step_id: Optional[str],
        status: str,
        attempt: int = 1,
        completed_step_ids: Iterable[str] = (),
    ) -> Dict[str, Any]:
        """构建统一的检查点载荷（Payload）字典。

        Args:
            task_id (str): 任务的唯一标识。
            run_id (str): 当前运行周期的唯一标识。
            last_completed_step_id (str): 最近一个成功完成的步骤 ID。
            next_step_id (Optional[str]): 即将执行的下一步骤 ID。
            status (str): 当前任务的状态值。
            attempt (int, optional): 当前运行周期或步骤的重试尝试次数。默认为 1。
            completed_step_ids (Iterable[str], optional): 所有已成功完成的步骤 ID 集合。默认为 ()。

        Returns:
            Dict[str, Any]: 结构化的检查点载荷字典。
        """
        return {
            "task_id": task_id,
            "run_id": run_id,
            "attempt": attempt,
            "last_completed_step_id": last_completed_step_id,
            "next_step_id": next_step_id,
            "status": status,
            "completed_step_ids": list(completed_step_ids),
        }

    def save_success_checkpoint(
        self,
        task: Task,
        *,
        run_id: str,
        last_completed_step_id: str,
        next_step_id: Optional[str],
        completed_step_ids: Iterable[str] = (),
        attempt: int = 1,
    ) -> Dict[str, Any]:
        """保存执行成功的步骤对应的检查点，并更新底层存储。

        Args:
            task (Task): 任务对象实例。
            run_id (str): 当前运行周期的唯一标识。
            last_completed_step_id (str): 最近一个成功完成的步骤 ID。
            next_step_id (Optional[str]): 即将执行的下一步骤 ID。
            completed_step_ids (Iterable[str], optional): 所有已成功完成的步骤 ID 集合。默认为 ()。
            attempt (int, optional): 重试尝试次数。默认为 1。

        Returns:
            Dict[str, Any]: 成功保存的检查点载荷。
        """
        payload = self.build_payload(
            task_id=task.task_id,
            run_id=run_id,
            last_completed_step_id=last_completed_step_id,
            next_step_id=next_step_id,
            status=task.status.value,
            attempt=attempt,
            completed_step_ids=completed_step_ids,
        )
        if self.storage is not None:
            # 兼容性检查：如果存储支持事务级检查点存储则优先调用，否则使用传统的键值覆盖存储
            save_transaction = getattr(self.storage, "save_transaction_checkpoint", None)
            if callable(save_transaction):
                save_transaction(task, payload)
            else:
                self.storage.save_checkpoint(task, last_completed_step_id, next_step_id)
        return payload


@dataclass
class CheckpointReplay:
    """基于工作流事件流动态重建的检查点状态回放器。

    该类可以通过对特定任务的历史事件进行有序回放，得出准确的已完成步骤、重试次数及失败断点。
    """

    task_id: str
    completed_step_ids: list[str]
    attempts_by_step: Dict[str, int]
    failed_step_id: Optional[str] = None
    last_run_id: Optional[str] = None

    @classmethod
    def from_events(cls, task_id: str, events: Iterable[Any]) -> "CheckpointReplay":
        """从给定的工作流事件集合中还原并构造 `CheckpointReplay` 实例。

        通过分析 started/completed/failed 等关键事件，重构出任务的历史运行轮廓。

        Args:
            task_id (str): 任务的唯一标识。
            events (Iterable[Any]): 结构化或字典形式的任务事件流。

        Returns:
            CheckpointReplay: 重建出的检查点回放状态实例。
        """
        completed: list[str] = []
        attempts: Dict[str, int] = {}
        failed_step_id: Optional[str] = None
        last_run_id: Optional[str] = None
        
        for event in events:
            event_type, payload = cls._event_parts(event)
            step_id = payload.get("step_id")
            if not step_id:
                continue
            step_id = str(step_id)
            if payload.get("run_id"):
                last_run_id = str(payload["run_id"])
            
            # 分析事件类型更新重试尝试与完成状态
            if event_type == "workflow.step.started":
                attempts[step_id] = attempts.get(step_id, 0) + 1
            elif event_type == "workflow.step.completed":
                if attempts.get(step_id, 0) == 0:
                    attempts[step_id] = 1
                if step_id not in completed:
                    completed.append(step_id)
                # 若之前标记为失败的步骤在随后成功完成，则清除失败标记
                if failed_step_id == step_id:
                    failed_step_id = None
            elif event_type == "workflow.step.failed":
                if attempts.get(step_id, 0) == 0:
                    attempts[step_id] = 1
                failed_step_id = step_id
                
        return cls(
            task_id=task_id,
            completed_step_ids=completed,
            attempts_by_step=attempts,
            failed_step_id=failed_step_id,
            last_run_id=last_run_id,
        )

    @staticmethod
    def _event_parts(event: Any) -> tuple[str, Dict[str, Any]]:
        """从事件对象或字典中提取事件类型和载荷。

        Args:
            event (Any): 事件对象（可能为字典或包含特定属性的类实例）。

        Returns:
            tuple[str, Dict[str, Any]]: (事件类型, 事件载荷字典) 二元组。
        """
        if isinstance(event, dict):
            return str(event.get("type", "")), dict(event.get("payload", {}))
        return str(getattr(event, "type", "")), dict(getattr(event, "payload", {}) or {})

    def next_attempt_for(self, step_id: str) -> int:
        """获取指定步骤在下次运行时应当使用的尝试次数。

        Args:
            step_id (str): 步骤 ID。

        Returns:
            int: 下次执行的尝试序数（当前已尝试次数加 1）。
        """
        return self.attempts_by_step.get(step_id, 1) + 1

    def to_checkpoint_payload(self, next_step_id: Optional[str], status: str = "running") -> Dict[str, Any]:
        """将当前回放器的状态转换为统一的检查点载荷格式。

        Args:
            next_step_id (Optional[str]): 即将执行的下一步骤 ID。
            status (str, optional): 任务运行状态。默认为 "running"。

        Returns:
            Dict[str, Any]: 结构化的检查点载荷。
        """
        return {
            "task_id": self.task_id,
            "last_completed_step_id": self.completed_step_ids[-1] if self.completed_step_ids else None,
            "next_step_id": next_step_id,
            "status": status,
            "completed_step_ids": list(self.completed_step_ids),
            "attempts_by_step": dict(self.attempts_by_step),
            "failed_step_id": self.failed_step_id,
            "last_run_id": self.last_run_id,
        }
