"""旧任务执行链的显式懒加载隔离。

EvoCanvas Canvas 主链只使用 Pi Runtime。旧任务 API 仍作为迁移资产保留时，
只有真正访问旧任务执行能力才创建旧 WorkflowEngine，避免它在普通 Canvas
请求启动时成为第二个在线模型入口。
"""

from __future__ import annotations

from threading import RLock
from typing import Any, Callable


class LazyLegacyWorkflowEngine:
    """延迟创建并代理旧 WorkflowEngine；不参与 Canvas 主链。"""

    def __init__(self, factory: Callable[[], Any]) -> None:
        self._factory = factory
        self._engine: Any | None = None
        self._lock = RLock()

    @property
    def initialized(self) -> bool:
        return self._engine is not None

    def _get(self) -> Any:
        if self._engine is None:
            with self._lock:
                if self._engine is None:
                    self._engine = self._factory()
        return self._engine

    @property
    def llm(self) -> Any:
        return self._get().llm

    @property
    def tool_service(self) -> Any:
        return self._get().tool_service

    def run(self, task: Any, until_step_id: str | None = None) -> Any:
        return self._get().run(task, until_step_id=until_step_id)

    def apply_decision(self, task: Any, **kwargs: Any) -> Any:
        return self._get().apply_decision(task, **kwargs)

    def cancel(self, task: Any) -> Any:
        return self._get().cancel(task)
