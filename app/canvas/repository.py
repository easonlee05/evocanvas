"""EvoCanvas 工作区仓储。

当前实现覆盖 EvoCanvas 1.0 首批落盘对象：
- 在 `canvas/workspaces/{workspace_id}/workspace.json` 下保存工作区根对象
- 从同一路径加载工作区根对象
- 按 workspace 维度维护 confirmation queue
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Optional, Protocol, Sequence

from app.canvas.domain.cards import CanvasCard
from app.canvas.domain.handoff import StructuredHandoff
from app.canvas.domain.mutations import CanvasMutationProposal
from app.canvas.domain.relations import CanvasRelation
from app.canvas.domain.snapshots import CanvasSnapshot
from app.canvas.domain.workspace import CanvasWorkspace


class CanvasStorage(Protocol):
    """约束 EvoCanvas 仓储所需的最小底层存储接口。"""

    def canvas_root(self) -> Path:
        """返回 EvoCanvas 工作区持久化根目录。"""


class CanvasRepository:
    """面向 EvoCanvas 工作区根对象的最小文件仓储。"""

    _workspace_locks: dict[str, threading.Lock] = {}
    _workspace_locks_guard = threading.Lock()

    def __init__(self, storage: CanvasStorage):
        """基于现有底座存储实例初始化仓储。

        Args:
            storage: 提供 `canvas_root()` 的底层存储对象。
        """
        self.storage = storage

    def _workspace_dir(self, workspace_id: str) -> Path:
        """返回指定工作区的持久化目录，并在保存前确保目录存在。"""

        return self.storage.canvas_root() / "workspaces" / workspace_id

    @classmethod
    def _workspace_lock(cls, workspace_id: str) -> threading.Lock:
        with cls._workspace_locks_guard:
            if workspace_id not in cls._workspace_locks:
                cls._workspace_locks[workspace_id] = threading.Lock()
            return cls._workspace_locks[workspace_id]

    def save_workspace(self, workspace: CanvasWorkspace) -> None:
        """持久化工作区根对象到首版约定路径。"""

        workspace_dir = self._workspace_dir(workspace.workspace_id)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        self._write_json_atomic(workspace_dir / "workspace.json", workspace.to_dict())

    def load_workspace(self, workspace_id: str) -> Optional[CanvasWorkspace]:
        """从首版约定路径读取工作区根对象。"""

        path = self._workspace_dir(workspace_id) / "workspace.json"
        if not path.exists():
            return None
        return CanvasWorkspace.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def claim_active_turn(self, workspace_id: str, turn_id: str, started_at: str) -> Optional[CanvasWorkspace]:
        """尝试为工作区占用一个新的 active turn。

        当工作区仍有未释放的回合时返回 None，否则返回更新后的工作区对象。
        """

        with self._workspace_lock(workspace_id):
            workspace = self.load_workspace(workspace_id)
            if workspace is None:
                return None
            if workspace.active_turn_id and workspace.active_turn_status != "idle":
                return None
            workspace.active_turn_id = turn_id
            workspace.active_turn_status = "running"
            workspace.active_turn_started_at = started_at
            self.save_workspace(workspace)
            return workspace

    def mark_turn_awaiting_confirmation(self, workspace_id: str, turn_id: str) -> Optional[CanvasWorkspace]:
        """将匹配的 active turn 标记为等待确认。"""

        with self._workspace_lock(workspace_id):
            workspace = self.load_workspace(workspace_id)
            if workspace is None or workspace.active_turn_id != turn_id:
                return workspace
            workspace.active_turn_status = "awaiting_confirmation"
            self.save_workspace(workspace)
            return workspace

    def release_active_turn(self, workspace_id: str, turn_id: str) -> Optional[CanvasWorkspace]:
        """释放匹配的 active turn；若 turn 不匹配则保持原样返回。"""

        with self._workspace_lock(workspace_id):
            workspace = self.load_workspace(workspace_id)
            if workspace is None or workspace.active_turn_id != turn_id:
                return workspace
            workspace.active_turn_id = ""
            workspace.active_turn_status = "idle"
            workspace.active_turn_started_at = ""
            self.save_workspace(workspace)
            return workspace

    def save_confirmation_queue(
        self,
        workspace_id: str,
        proposals: Sequence[CanvasMutationProposal],
    ) -> None:
        """按工作区维度持久化待确认提案队列。"""

        workspace_dir = self._workspace_dir(workspace_id)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        queue_file = workspace_dir / "confirmation_queue.json"
        self._write_json_atomic(queue_file, {"items": [proposal.to_dict() for proposal in proposals]})

    def load_confirmation_queue(self, workspace_id: str) -> list[CanvasMutationProposal]:
        """读取工作区级待确认提案队列。"""

        queue_file = self._workspace_dir(workspace_id) / "confirmation_queue.json"
        if not queue_file.exists():
            return []
        payload = json.loads(queue_file.read_text(encoding="utf-8"))
        return [CanvasMutationProposal.from_dict(item) for item in payload.get("items", [])]

    def save_cards(self, workspace_id: str, cards: Sequence[CanvasCard]) -> None:
        """持久化工作区当前画布卡片集合。"""

        workspace_dir = self._workspace_dir(workspace_id)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        cards_file = workspace_dir / "cards.json"
        self._write_json_atomic(cards_file, {"items": [card.to_dict() for card in cards]})

    def load_cards(self, workspace_id: str) -> list[CanvasCard]:
        """读取工作区当前画布卡片集合。"""

        cards_file = self._workspace_dir(workspace_id) / "cards.json"
        if not cards_file.exists():
            return []
        payload = json.loads(cards_file.read_text(encoding="utf-8"))
        return [CanvasCard.from_dict(item) for item in payload.get("items", [])]

    def save_relations(self, workspace_id: str, relations: Sequence[CanvasRelation]) -> None:
        """持久化工作区当前画布关系集合。"""

        workspace_dir = self._workspace_dir(workspace_id)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        relations_file = workspace_dir / "relations.json"
        self._write_json_atomic(relations_file, {"items": [relation.to_dict() for relation in relations]})

    def load_relations(self, workspace_id: str) -> list[CanvasRelation]:
        """读取工作区当前画布关系集合。"""

        relations_file = self._workspace_dir(workspace_id) / "relations.json"
        if not relations_file.exists():
            return []
        payload = json.loads(relations_file.read_text(encoding="utf-8"))
        return [CanvasRelation.from_dict(item) for item in payload.get("items", [])]

    def save_handoff(self, workspace_id: str, handoff: StructuredHandoff) -> None:
        """持久化工作区当前结构化交接物草稿。"""

        workspace_dir = self._workspace_dir(workspace_id)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        handoff_file = workspace_dir / "handoff.json"
        self._write_json_atomic(handoff_file, handoff.to_dict())

    def load_handoff(self, workspace_id: str) -> Optional[StructuredHandoff]:
        """读取工作区当前结构化交接物草稿。"""

        handoff_file = self._workspace_dir(workspace_id) / "handoff.json"
        if not handoff_file.exists():
            return None
        return StructuredHandoff.from_dict(json.loads(handoff_file.read_text(encoding="utf-8")))

    def save_snapshot(self, workspace_id: str, snapshot: CanvasSnapshot) -> None:
        """保存一份工作区快照。"""

        snapshots_dir = self._workspace_dir(workspace_id) / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        snapshot_file = snapshots_dir / f"{snapshot.snapshot_id}.json"
        self._write_json_atomic(snapshot_file, snapshot.to_dict())

    def list_snapshots(self, workspace_id: str) -> list[CanvasSnapshot]:
        """列出工作区已保存的快照。"""

        snapshots_dir = self._workspace_dir(workspace_id) / "snapshots"
        if not snapshots_dir.exists():
            return []
        snapshots: list[CanvasSnapshot] = []
        for path in sorted(snapshots_dir.glob("*.json")):
            snapshots.append(CanvasSnapshot.from_dict(json.loads(path.read_text(encoding="utf-8"))))
        return snapshots

    def load_snapshot(self, workspace_id: str, snapshot_id: Optional[str]) -> Optional[CanvasSnapshot]:
        """按 ID 读取一份工作区快照。"""

        if not snapshot_id:
            return None
        snapshot_file = self._workspace_dir(workspace_id) / "snapshots" / f"{snapshot_id}.json"
        if not snapshot_file.exists():
            return None
        return CanvasSnapshot.from_dict(json.loads(snapshot_file.read_text(encoding="utf-8")))

    def append_proposal_history(self, workspace_id: str, proposal: CanvasMutationProposal) -> None:
        """追加记录一条提案历史，便于回看 AI 或用户建议的变化包。"""

        workspace_dir = self._workspace_dir(workspace_id)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        history_file = workspace_dir / "proposal_history.jsonl"
        with history_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(proposal.to_dict(), ensure_ascii=False) + "\n")

    def load_proposal_history(self, workspace_id: str) -> list[CanvasMutationProposal]:
        """读取工作区提案历史。"""

        history_file = self._workspace_dir(workspace_id) / "proposal_history.jsonl"
        if not history_file.exists():
            return []
        proposals = []
        for line in history_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                proposals.append(CanvasMutationProposal.from_dict(json.loads(line)))
        return proposals

    @staticmethod
    def _write_json_atomic(path: Path, payload) -> None:
        tmp_path = path.with_name(f"{path.name}.{threading.get_ident()}.tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp_path, path)
