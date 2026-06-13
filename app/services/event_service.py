"""结构化审计事件的发布与回放服务。

本模块提供统一的事件发射（emit）与回放（replay）接口，
底层对接存储适配器的事件持久化机制（如 events.jsonl）以及 EventBus 消息订阅发布流，
用于前端 SSE 链路的事件流式订阅或任务执行过程的实时审计。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.events import Event


class EventService:
    """事件发射与回放核心服务类。

    管理工作流/Agent 节点运行态中生命周期事件的捕获与持久化。
    """

    def __init__(self, storage: Any):
        """初始化 EventService 实例。

        Args:
            storage: 底座持久化存储适配器。
        """
        self.storage = storage

    def emit(self, task_id: str, event_type: str, payload: Dict[str, Any] | None = None, role: Optional[str] = None, status: Optional[str] = None) -> Event:
        """构建一个新的结构化事件实体，并持久化发布。

        通过调用存储器的 `append_event` 将事件追加落盘并广播至 EventBus。

        Args:
            task_id: 关联的任务 ID。
            event_type: 事件类型（如 'agent.message.chunk', 'task.started'）。
            payload: 事件携带的具体上下文载荷字典。
            role: 产生该事件的执行角色标识。
            status: 事件发生的具体状态。

        Returns:
            Event: 持久化并填充好 ID 等字段的 Event 实体。
        """
        event = Event(task_id=task_id, type=event_type, payload=payload or {}, role=role, status=status)
        return self.storage.append_event(event)

    def replay(self, task_id: str) -> List[Event]:
        """回放指定任务的所有历史审计事件列表。

        主要用于从 events.jsonl 中重载历史步骤状态或供前端拉取渲染。

        Args:
            task_id: 任务唯一标识符。

        Returns:
            List[Event]: 该任务的结构化审计事件列表。
        """
        return self.storage.read_events(task_id)

