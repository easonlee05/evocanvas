"""EvoCanvas 核心契约层结构化事件与 Trace 追踪定义。

该模块为 API/SSE 消费者以及审计总线提供了统一的结构化事件流模型、Trace Span 模型和进程内事件发布订阅总线（EventBus）。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
import queue
from collections import defaultdict


def utc_now_iso() -> str:
    """获取当前 UTC 时间的 ISO 8601 格式字符串。

    Returns:
        str: 当前时间的 ISO 格式字符串（例如 "2026-06-05T01:08:51.123456+00:00"）。
    """
    return datetime.now(timezone.utc).isoformat()

@dataclass
class TraceSpan:
    """TraceSpan 追踪跨度模型，用于记录任务执行过程中各个步骤或工具调用的调用链路信息。

    Attributes:
        span_id: 唯一的 Span ID。
        task_id: 关联的 Task ID。
        name: Span 名称（如具体步骤名称或工具名称）。
        type: Span 类型（如 'step' 或 'tool'）。
        start_time: 开始时间，ISO 8601 格式，默认为当前 UTC 时间。
        parent_span_id: 父级 Span ID，用于构建调用链路树。
        end_time: 结束时间，ISO 8601 格式，执行完成后填充。
        attributes: 键值对形式的属性集，用于审计或详细诊断。
        status: 执行状态，通常为 "ok"、"error" 等。
    """
    span_id: str
    task_id: str
    name: str
    type: str
    start_time: str = field(default_factory=utc_now_iso)
    parent_span_id: Optional[str] = None
    end_time: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "ok"

    def to_dict(self) -> Dict[str, Any]:
        """将 TraceSpan 对象转换成字典格式。

        Returns:
            Dict[str, Any]: 转换后的字典。
        """
        return asdict(self)


@dataclass
class Event:
    """结构化事件模型，用于在事件总线上进行流式分发、持久化以及通过 SSE 实时同步给前端。

    Attributes:
        task_id: 关联的任务 ID。
        type: 事件类型（如 'task.started', 'tool.call.started', 'decision.waiting' 等）。
        payload: 包含具体事件内容的字典。
        role: 触发或关联的角色（例如 'compiler', 'reviewer'）。
        status: 事件关联的状态。
        id: 事件唯一标识 UUID 串，默认为空。
        created_at: 事件创建的 ISO 8601 时间戳。
    """
    task_id: str
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    role: Optional[str] = None
    status: Optional[str] = None
    id: str = ""
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        """将 Event 对象转换成字典格式。

        Returns:
            Dict[str, Any]: 转换后的字典。
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """从字典反序列化生成 Event 对象。

        Args:
            data: 包含 Event 字段的字典。

        Returns:
            Event: 反序列化出的事件实体。
        """
        return cls(
            id=data.get("id", ""),
            task_id=data["task_id"],
            type=data["type"],
            role=data.get("role"),
            status=data.get("status"),
            payload=data.get("payload", {}),
            created_at=data.get("created_at", utc_now_iso()),
        )

class EventBus:
    """进程内事件总线，负责为不同任务分发订阅队列，支持前端 SSE 消费和审计记录。"""
    def __init__(self):
        """初始化事件总线，设置订阅者映射表。"""
        # 使用 defaultdict(list) 存储 task_id 到 queue.Queue 的列表映射
        self.subscribers: Dict[str, List[queue.Queue]] = defaultdict(list)
        
    def subscribe(self, task_id: str) -> queue.Queue:
        """订阅指定任务的事件流。

        Args:
            task_id: 需要订阅的任务 ID。

        Returns:
            queue.Queue: 该任务的专属事件同步队列。
        """
        q = queue.Queue()
        self.subscribers[task_id].append(q)
        return q
        
    def unsubscribe(self, task_id: str, q: queue.Queue) -> None:
        """退订指定任务的事件流，移除对应的事件队列。

        Args:
            task_id: 需要退订的任务 ID。
            q: 之前订阅时创建的事件队列。
        """
        if task_id in self.subscribers and q in self.subscribers[task_id]:
            self.subscribers[task_id].remove(q)
            
    def publish(self, event: Event) -> None:
        """向特定任务的所有订阅队列广播推送事件。

        Args:
            event: 要发布的结构化事件实体。
        """
        # 遍历所有订阅了该任务 ID 的队列并压入事件
        for q in self.subscribers.get(event.task_id, []):
            q.put(event)
