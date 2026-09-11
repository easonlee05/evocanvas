"""EvoCanvas 工作区仓储。

当前实现覆盖 EvoCanvas 1.0 首批落盘对象：
- 在 `canvas/workspaces/{workspace_id}/workspace.json` 下保存工作区根对象
- 从同一路径加载工作区根对象
- 结构化包（Package）与不可变包版本（PackageVersion）的持久化与查询
- 追加式状态账本（StateLedger）事件流
- 不可改写的确认记录（ConfirmationRecord）

L3 规格明确：confirmation_queue 只保留为历史提案或消息证据，不转换为新的审批任务。
因此本仓储不再提供 confirmation_queue 的写入入口，改为提供 ConfirmationRecord 仓储。
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Protocol, Sequence
from uuid import uuid4

from app.canvas.domain.cards import CanvasCard
from app.canvas.domain.confirmation import ConfirmationRecord
from app.canvas.domain.handoff import StructuredHandoff
from app.canvas.domain.ledger import LedgerEvent
from app.canvas.domain.mutations import CanvasMutationProposal
from app.canvas.domain.package import InitialGovernanceStatus, Package, PackageVersion
from app.canvas.domain.relations import CanvasRelation
from app.canvas.domain.runtime_records import (
    ChatTurnRecord,
    CommitAttemptRecord,
    ConvergenceJudgementRecord,
    ConvergenceRunRecord,
    OutboxEntry,
    PackageLease,
)
from app.canvas.domain.snapshots import CanvasSnapshot
from app.canvas.domain.workspace import CanvasWorkspace


class CanvasStorage(Protocol):
    """约束 EvoCanvas 仓储所需的最小底层存储接口。"""

    def canvas_root(self) -> Path:
        """返回 EvoCanvas 工作区持久化根目录。"""


class PackageVersionStaleError(ValueError):
    """提交基准版本已变化；不得重放旧提案。"""

    code = "base_version_changed"

    def __init__(self, package_id: str, expected_package_version: int, actual_package_version: int, expected_state_version: int, actual_state_version: int):
        super().__init__(
            f"package {package_id} base version changed: expected v{expected_package_version}/s{expected_state_version}, "
            f"actual v{actual_package_version}/s{actual_state_version}"
        )
        self.package_id = package_id
        self.expected_package_version = expected_package_version
        self.actual_package_version = actual_package_version
        self.expected_state_version = expected_state_version
        self.actual_state_version = actual_state_version


import re


def _safe_id(value: str) -> str:
    """严格校验工作区与包标识符格式，防范路径穿越。"""
    if not value or not re.match(r"^[a-zA-Z0-9_-]+$", str(value)):
        raise ValueError(f"invalid identifier: {value!r}")
    return str(value)


class CanvasRepository:
    """面向 EvoCanvas 工作区根对象的最小文件仓储。"""

    _workspace_locks: dict[str, Any] = {}
    _workspace_locks_guard = threading.Lock()

    def __init__(self, storage: CanvasStorage):
        """基于现有底座存储实例初始化仓储。

        Args:
            storage: 提供 `canvas_root()` 的底层存储对象。
        """
        self.storage = storage

    def _workspace_dir(self, workspace_id: str) -> Path:
        """返回指定工作区的持久化目录，并在保存前确保目录存在。"""
        safe_id = _safe_id(workspace_id)
        return self.storage.canvas_root() / "workspaces" / safe_id

    @classmethod
    def _workspace_lock(cls, workspace_id: str) -> Any:
        with cls._workspace_locks_guard:
            if workspace_id not in cls._workspace_locks:
                # 提交路径会在同一工作区内读取现有账本和包指针，需允许可重入锁。
                cls._workspace_locks[workspace_id] = threading.RLock()
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

    def list_workspaces(self) -> list[CanvasWorkspace]:
        """列出所有已持久化工作区，并按最近更新时间倒序返回。"""

        workspaces_dir = self.storage.canvas_root() / "workspaces"
        if not workspaces_dir.exists():
            return []

        items: list[CanvasWorkspace] = []
        for path in sorted(workspaces_dir.glob("*/workspace.json")):
            items.append(CanvasWorkspace.from_dict(json.loads(path.read_text(encoding="utf-8"))))

        return sorted(
            items,
            key=lambda item: (item.updated_at or item.created_at or "", item.workspace_id),
            reverse=True,
        )

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

    # ------------------------------------------------------------------
    # 结构化包（Package）与不可变包版本（PackageVersion）
    # ------------------------------------------------------------------

    def _package_dir(self, workspace_id: str, package_id: str) -> Path:
        """返回指定包的持久化目录。"""
        safe_pkg = _safe_id(package_id)
        return self._workspace_dir(workspace_id) / "packages" / safe_pkg

    def save_package(self, workspace_id: str, package: Package) -> None:
        """持久化结构化包根对象。"""

        package_dir = self._package_dir(workspace_id, package.package_id)
        package_dir.mkdir(parents=True, exist_ok=True)
        self._write_json_atomic(package_dir / "package.json", package.to_dict())

    def load_package(self, workspace_id: str, package_id: str) -> Optional[Package]:
        """读取结构化包根对象。"""

        path = self._package_dir(workspace_id, package_id) / "package.json"
        if not path.exists():
            return None
        return Package.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_packages(self, workspace_id: str) -> list[Package]:
        """列出工作区下所有结构化包。"""

        packages_dir = self._workspace_dir(workspace_id) / "packages"
        if not packages_dir.exists():
            return []
        items: list[Package] = []
        for path in sorted(packages_dir.glob("*/package.json")):
            items.append(Package.from_dict(json.loads(path.read_text(encoding="utf-8"))))
        return items

    def save_package_version(
        self,
        workspace_id: str,
        version: PackageVersion,
    ) -> None:
        """持久化不可变包版本，拒绝同版本号的任何覆写。"""

        package_dir = self._package_dir(workspace_id, version.package_id)
        versions_dir = package_dir / "versions"
        versions_dir.mkdir(parents=True, exist_ok=True)
        version_file = versions_dir / f"v{version.package_version}.json"
        if version_file.exists():
            raise FileExistsError(
                f"package version already exists and is immutable: {version.package_id} v{version.package_version}"
            )
        version.content_checksum = self.package_version_checksum(version)
        self._write_json_atomic(version_file, version.to_dict())

    def load_package_version(
        self,
        workspace_id: str,
        package_id: str,
        package_version: int,
    ) -> Optional[PackageVersion]:
        """按版本号读取不可变包版本。"""

        version_file = (
            self._package_dir(workspace_id, package_id)
            / "versions"
            / f"v{package_version}.json"
        )
        if not version_file.exists():
            return None
        version = PackageVersion.from_dict(json.loads(version_file.read_text(encoding="utf-8")))
        expected_checksum = self.package_version_checksum(version)
        if version.content_checksum != expected_checksum:
            raise ValueError(
                f"package version checksum mismatch: {package_id} v{package_version}"
            )
        return version

    def list_package_versions(
        self,
        workspace_id: str,
        package_id: str,
    ) -> list[PackageVersion]:
        """列出指定包的所有不可变版本，按版本号升序返回。"""

        versions_dir = self._package_dir(workspace_id, package_id) / "versions"
        if not versions_dir.exists():
            return []
        versions: list[PackageVersion] = []
        for path in sorted(versions_dir.glob("v*.json"), key=lambda item: int(item.stem[1:])):
            versions.append(self.load_package_version(workspace_id, package_id, int(path.stem[1:])))
        return versions

    @staticmethod
    def package_version_checksum(version: PackageVersion) -> str:
        """计算包版本正文校验和，不把校验和字段本身纳入摘要。"""

        payload = version.to_dict()
        payload.pop("content_checksum", None)
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(canonical.encode("utf-8")).hexdigest()

    def load_active_package(self, workspace_id: str) -> Optional[Package]:
        """读取工作区当前活跃包；画布投影只能从该包的当前版本取得。"""

        active_packages = [
            package
            for package in self.list_packages(workspace_id)
            if package.lifecycle_status.value == "active"
        ]
        if not active_packages:
            return None
        return max(active_packages, key=lambda item: (item.updated_at, item.package_id))

    def load_active_package_version(self, workspace_id: str) -> Optional[PackageVersion]:
        """读取当前活跃包所指向的不可变版本。"""

        package = self.load_active_package(workspace_id)
        if package is None or package.current_version <= 0:
            return None
        return self.load_package_version(workspace_id, package.package_id, package.current_version)

    def commit_package_version(
        self,
        workspace_id: str,
        package: Package,
        version: PackageVersion,
        events: Sequence[LedgerEvent],
        confirmation: Optional[ConfirmationRecord] = None,
        outbox_entries: Sequence[OutboxEntry] = (),
    ) -> Package:
        """原子可见地提交一个新的包版本、账本事件和可选确认记录。

        版本正文、确认记录和账本先写入不可变位置；最后原子更新包根指针，
        因而读取方只能看到上一个完整版本或这个完整版本。相同 operation_id
        在同一工作区内幂等返回既有包，不会重复推进 state_version 或追加事件。
        """

        if package.workspace_id != workspace_id or version.package_id != package.package_id:
            raise ValueError("package commit workspace/package identity mismatch")
        if not version.operation_id:
            raise ValueError("package version commit requires operation_id")

        with self._workspace_lock(workspace_id):
            if self.has_operation_id(workspace_id, version.operation_id):
                existing = self.load_package(workspace_id, package.package_id)
                if existing is None:
                    raise RuntimeError("ledger contains operation without package root")
                return existing

            previous = self.load_package(workspace_id, package.package_id)
            expected_version = (previous.current_version if previous is not None else 0) + 1
            expected_state_version = (previous.state_version if previous is not None else 0) + 1
            if version.package_version != expected_version:
                raise PackageVersionStaleError(
                    package.package_id,
                    expected_version - 1,
                    previous.current_version if previous is not None else 0,
                    expected_state_version - 1,
                    previous.state_version if previous is not None else 0,
                )
            if version.state_version != expected_state_version:
                raise PackageVersionStaleError(
                    package.package_id,
                    version.package_version - 1,
                    previous.current_version if previous is not None else 0,
                    expected_state_version - 1,
                    previous.state_version if previous is not None else 0,
                )
            if version.parent_version != (previous.current_version if previous else None):
                raise PackageVersionStaleError(
                    package.package_id,
                    version.parent_version or 0,
                    previous.current_version if previous is not None else 0,
                    version.state_version - 1,
                    previous.state_version if previous is not None else 0,
                )
            if any(event.package_id != package.package_id for event in events):
                raise ValueError("ledger event package_id does not match committed package")
            if any(
                entry.workspace_id != workspace_id
                or entry.package_id != package.package_id
                or entry.operation_id != version.operation_id
                for entry in outbox_entries
            ):
                raise ValueError("outbox entry identity does not match committed package operation")

            package.current_version = version.package_version
            package.state_version = version.state_version
            if version.initial_governance_status == InitialGovernanceStatus.CONFIRMED:
                package.latest_confirmed_version = version.package_version

            # 包根指针是提交可见性的最后一步，之前的写入不会覆盖任何历史正文。
            self.save_package_version(workspace_id, version)
            if confirmation is not None:
                self.save_confirmation_record(workspace_id, confirmation)
            self._append_ledger_events_atomically(workspace_id, events)
            for entry in outbox_entries:
                self.enqueue_outbox(entry)
            self.save_package(workspace_id, package)
            return package

    # ------------------------------------------------------------------
    # 追加式状态账本（StateLedger）
    # ------------------------------------------------------------------

    def append_ledger_event(
        self,
        workspace_id: str,
        event: LedgerEvent,
    ) -> None:
        """向状态账本追加一条事件。

        账本以 JSONL 文件追加保存，不覆盖历史事件；查询通过 query_ledger_events。
        """

        self.append_ledger_events(workspace_id, [event])

    def append_ledger_events(
        self,
        workspace_id: str,
        events: Sequence[LedgerEvent],
    ) -> None:
        """向状态账本批量追加事件，用于同提交升级的原子写入。"""

        if not events:
            return
        with self._workspace_lock(workspace_id):
            self._append_ledger_events_atomically(workspace_id, events)

    def _append_ledger_events_atomically(
        self,
        workspace_id: str,
        events: Sequence[LedgerEvent],
    ) -> None:
        """把既有账本与新增事件整体原子替换，避免批量提交出现半行记录。"""

        if not events:
            return
        workspace_dir = self._workspace_dir(workspace_id)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        ledger_file = workspace_dir / "state_ledger.jsonl"
        existing = ledger_file.read_text(encoding="utf-8") if ledger_file.exists() else ""
        suffix = "" if not existing or existing.endswith("\n") else "\n"
        appended = "".join(
            json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True) + "\n"
            for event in events
        )
        self._write_text_atomic(ledger_file, existing + suffix + appended)

    def query_ledger_events(
        self,
        workspace_id: str,
        *,
        package_id: Optional[str] = None,
        package_version: Optional[int] = None,
        entity_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        convergence_run_id: Optional[str] = None,
        confirmation_id: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> list[LedgerEvent]:
        """按多个键查询账本事件。

        任意过滤键为 None 时不限制该维度；至少支持按 package_id、package_version、
        object_id、operation_id、convergence_run_id、confirmation_id、event_type 查询。
        """

        ledger_file = self._workspace_dir(workspace_id) / "state_ledger.jsonl"
        if not ledger_file.exists():
            return []
        results: list[LedgerEvent] = []
        for line in ledger_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if package_id is not None and payload.get("package_id") != package_id:
                continue
            if package_version is not None and payload.get("package_version") != package_version:
                continue
            if entity_id is not None and payload.get("entity_id") != entity_id:
                continue
            if operation_id is not None and payload.get("operation_id") != operation_id:
                continue
            if (
                convergence_run_id is not None
                and payload.get("convergence_run_id") != convergence_run_id
            ):
                continue
            if confirmation_id is not None and payload.get("confirmation_id") != confirmation_id:
                continue
            if event_type is not None and payload.get("event_type") != event_type:
                continue
            results.append(LedgerEvent.from_dict(payload))
        return results

    def has_operation_id(self, workspace_id: str, operation_id: str) -> bool:
        """判断给定幂等键是否已在账本中出现，用于原子提交幂等校验。"""

        if not operation_id:
            return False
        return any(
            event.operation_id == operation_id
            for event in self.query_ledger_events(workspace_id)
        )

    # ------------------------------------------------------------------
    # 确认记录（ConfirmationRecord）
    # ------------------------------------------------------------------

    def save_confirmation_record(
        self,
        workspace_id: str,
        record: ConfirmationRecord,
    ) -> None:
        """持久化不可改写的确认记录。

        确认记录一经写入不可改写；撤回通过追加 confirmation_withdrawn 账本事件
        与新确认记录表达，不修改本记录。
        """

        confirmations_dir = self._workspace_dir(workspace_id) / "confirmations"
        confirmations_dir.mkdir(parents=True, exist_ok=True)
        record_file = confirmations_dir / f"{record.confirmation_id}.json"
        if record_file.exists():
            raise FileExistsError(
                f"confirmation record already exists and is immutable: {record.confirmation_id}"
            )
        self._write_json_atomic(record_file, record.to_dict())

    def load_confirmation_record(
        self,
        workspace_id: str,
        confirmation_id: str,
    ) -> Optional[ConfirmationRecord]:
        """按 ID 读取确认记录。"""

        record_file = (
            self._workspace_dir(workspace_id) / "confirmations" / f"{confirmation_id}.json"
        )
        if not record_file.exists():
            return None
        return ConfirmationRecord.from_dict(json.loads(record_file.read_text(encoding="utf-8")))

    def list_confirmation_records(
        self,
        workspace_id: str,
        package_id: Optional[str] = None,
    ) -> list[ConfirmationRecord]:
        """列出工作区下的确认记录，可按 package_id 过滤。"""

        confirmations_dir = self._workspace_dir(workspace_id) / "confirmations"
        if not confirmations_dir.exists():
            return []
        records: list[ConfirmationRecord] = []
        for path in sorted(confirmations_dir.glob("*.json")):
            record = ConfirmationRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
            if package_id is not None and record.package_id != package_id:
                continue
            records.append(record)
        return records

    def save_cards(self, workspace_id: str, cards: Sequence[CanvasCard]) -> None:
        """持久化工作区当前画布卡片集合。"""

        workspace_dir = self._workspace_dir(workspace_id)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        cards_file = workspace_dir / "cards.json"
        self._write_json_atomic(cards_file, {"items": [card.to_dict() for card in cards]})

    def load_cards(self, workspace_id: str) -> list[CanvasCard]:
        """读取当前包版本的画布卡片；历史 cards.json 仅作为首读来源。"""

        active_version = self.load_active_package_version(workspace_id)
        if active_version is not None:
            return [CanvasCard.from_dict(item) for item in active_version.objects]

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
        """读取当前包版本的关系；历史 relations.json 仅作为首读来源。"""

        active_version = self.load_active_package_version(workspace_id)
        if active_version is not None:
            return [CanvasRelation.from_dict(item) for item in active_version.relations]

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
        """读取当前包版本的交接模块；历史 handoff.json 只用于首读。"""

        active_version = self.load_active_package_version(workspace_id)
        if active_version is not None:
            return (
                StructuredHandoff.from_dict(active_version.handoff)
                if active_version.handoff is not None
                else None
            )

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

    def append_chat_message(self, workspace_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """追加保存一条正常 Chat 消息，供确认记录回指真实对话依据。

        该消息流不是审批队列：它只记录用户与助手在普通 Chat 中已经发生的
        表达，确认记录会引用其中明确的提议消息和用户回应消息。
        """

        message_id = str(message.get("message_id", "")).strip()
        role = str(message.get("role", "")).strip()
        content = str(message.get("content", "")).strip()
        if not message_id or role not in {"user", "assistant", "system"} or not content:
            raise ValueError("chat message requires message_id, supported role, and non-empty content")
        workspace_dir = self._workspace_dir(workspace_id)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        messages_file = workspace_dir / "chat_messages.jsonl"
        with self._workspace_lock(workspace_id):
            existing = self.load_chat_messages(workspace_id)
            if any(item.get("message_id") == message_id for item in existing):
                raise FileExistsError(f"chat message already exists: {message_id}")
            # message_seq 是会话内唯一的语义顺序；旧 JSONL 没有该字段时按历史
            # 追加顺序补齐，但不接受调用方跳号或回写旧序号。
            next_message_seq = max(
                (int(item.get("message_seq", index + 1)) for index, item in enumerate(existing)),
                default=0,
            ) + 1
            supplied_message_seq = message.get("message_seq")
            if supplied_message_seq is not None and int(supplied_message_seq) != next_message_seq:
                raise ValueError(f"message_seq must be the next workspace sequence: {next_message_seq}")
            existing.append(
                {
                    "message_id": message_id,
                    "message_seq": next_message_seq,
                    "role": role,
                    "content": content,
                    "turn_id": str(message.get("turn_id", "")),
                    "created_at": str(message.get("created_at", "")),
                    "metadata": dict(message.get("metadata", {})),
                }
            )
            self._write_text_atomic(
                messages_file,
                "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in existing),
            )
        return existing[-1]

    def load_chat_messages(self, workspace_id: str) -> list[Dict[str, Any]]:
        """读取工作区普通 Chat 消息，按追加顺序返回。"""

        messages_file = self._workspace_dir(workspace_id) / "chat_messages.jsonl"
        if not messages_file.exists():
            return []
        messages: list[Dict[str, Any]] = []
        for index, line in enumerate(messages_file.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            item = dict(json.loads(line))
            # 只在内存视图中为旧记录补序号；下一次 append 会以同一顺序持久化。
            item.setdefault("message_seq", index)
            messages.append(item)
        return messages

    def last_message_seq(self, workspace_id: str) -> int:
        """返回工作区 Chat 消息的最新语义序号；没有消息时返回 0。"""

        messages = self.load_chat_messages(workspace_id)
        return max(
            (int(item.get("message_seq", index + 1)) for index, item in enumerate(messages)),
            default=0,
        )

    # ------------------------------------------------------------------
    # Pi 运行记录与包级租约
    # ------------------------------------------------------------------

    _RUNTIME_RECORD_ID_FIELDS = {
        "chat_turn": "chat_turn_id",
        "convergence_judgement": "judgement_id",
        "convergence_run": "convergence_run_id",
        "commit_attempt": "commit_attempt_id",
        "outbox_entry": "outbox_id",
    }

    def _runtime_records_file(self, workspace_id: str) -> Path:
        return self._workspace_dir(workspace_id) / "runtime_records.jsonl"

    def load_runtime_records(
        self,
        workspace_id: str,
        record_type: str | None = None,
    ) -> list[Dict[str, Any]]:
        """读取运行记录；不把记录投影为工作区或包状态。"""

        records_file = self._runtime_records_file(workspace_id)
        if not records_file.exists():
            return []
        records: list[Dict[str, Any]] = []
        for line in records_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = dict(json.loads(line))
            if record_type is None or payload.get("record_type") == record_type:
                records.append(payload)
        return records

    def _upsert_runtime_record(self, workspace_id: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        record_type = str(payload.get("record_type", ""))
        id_field = self._RUNTIME_RECORD_ID_FIELDS.get(record_type)
        if id_field is None:
            raise ValueError(f"unsupported runtime record type: {record_type}")
        record_id = str(payload.get(id_field, "")).strip()
        if not record_id:
            raise ValueError(f"runtime record requires {id_field}")
        with self._workspace_lock(workspace_id):
            records = self.load_runtime_records(workspace_id)
            replaced = False
            for index, existing in enumerate(records):
                if existing.get("record_type") == record_type and existing.get(id_field) == record_id:
                    records[index] = dict(payload)
                    replaced = True
                    break
            if not replaced:
                records.append(dict(payload))
            records_file = self._runtime_records_file(workspace_id)
            records_file.parent.mkdir(parents=True, exist_ok=True)
            self._write_text_atomic(
                records_file,
                "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in records),
            )
        return dict(payload)

    def save_chat_turn(self, record: ChatTurnRecord) -> ChatTurnRecord:
        self._upsert_runtime_record(record.workspace_id, record.to_dict())
        return record

    def load_chat_turn(self, workspace_id: str, chat_turn_id: str) -> ChatTurnRecord | None:
        return next(
            (
                ChatTurnRecord.from_dict(payload)
                for payload in self.load_runtime_records(workspace_id, "chat_turn")
                if payload.get("chat_turn_id") == chat_turn_id
            ),
            None,
        )

    def save_convergence_judgement(self, record: ConvergenceJudgementRecord) -> ConvergenceJudgementRecord:
        self._upsert_runtime_record(record.workspace_id, record.to_dict())
        return record

    def save_convergence_run(self, record: ConvergenceRunRecord) -> ConvergenceRunRecord:
        self._upsert_runtime_record(record.workspace_id, record.to_dict())
        return record

    def load_convergence_run(self, workspace_id: str, convergence_run_id: str) -> ConvergenceRunRecord | None:
        return next(
            (
                ConvergenceRunRecord.from_dict(payload)
                for payload in self.load_runtime_records(workspace_id, "convergence_run")
                if payload.get("convergence_run_id") == convergence_run_id
            ),
            None,
        )

    def save_commit_attempt(self, record: CommitAttemptRecord) -> CommitAttemptRecord:
        self._upsert_runtime_record(record.workspace_id, record.to_dict())
        return record

    def load_commit_attempt(self, workspace_id: str, commit_attempt_id: str) -> CommitAttemptRecord | None:
        return next(
            (
                CommitAttemptRecord.from_dict(payload)
                for payload in self.load_runtime_records(workspace_id, "commit_attempt")
                if payload.get("commit_attempt_id") == commit_attempt_id
            ),
            None,
        )

    def enqueue_outbox(self, entry: OutboxEntry) -> OutboxEntry:
        self._upsert_runtime_record(entry.workspace_id, entry.to_dict())
        return entry

    def load_outbox(self, workspace_id: str, status: str | None = None) -> list[OutboxEntry]:
        return [
            OutboxEntry.from_dict(payload)
            for payload in self.load_runtime_records(workspace_id, "outbox_entry")
            if status is None or payload.get("status") == status
        ]

    def mark_outbox(
        self,
        workspace_id: str,
        outbox_id: str,
        *,
        status: str,
        updated_at: str,
        last_error: str | None = None,
        increment_attempts: bool = False,
    ) -> OutboxEntry:
        """以同一 outbox_id 更新发送状态，恢复器可安全重复调用。"""

        entries = self.load_outbox(workspace_id)
        entry = next((item for item in entries if item.outbox_id == outbox_id), None)
        if entry is None:
            raise KeyError(f"outbox entry not found: {outbox_id}")
        updated = OutboxEntry(
            outbox_id=entry.outbox_id,
            workspace_id=entry.workspace_id,
            package_id=entry.package_id,
            operation_id=entry.operation_id,
            event_type=entry.event_type,
            payload=entry.payload,
            status=status,
            attempts=entry.attempts + (1 if increment_attempts else 0),
            created_at=entry.created_at,
            updated_at=updated_at,
            last_error=last_error,
        )
        self.enqueue_outbox(updated)
        return updated

    def load_judgement_watermark(self, workspace_id: str, conversation_id: str, package_id: str | None) -> int:
        path = self._workspace_dir(workspace_id) / "runtime" / "judgement_watermarks.json"
        if not path.exists():
            return 0
        payload = json.loads(path.read_text(encoding="utf-8"))
        key = f"{conversation_id}:{package_id or ''}"
        return int(payload.get(key, 0))

    def advance_judgement_watermark(
        self,
        workspace_id: str,
        conversation_id: str,
        package_id: str | None,
        through_message_seq: int,
    ) -> bool:
        """只允许水位前进；旧判断结果返回 False，不能覆盖最新范围。"""

        if through_message_seq < 0:
            raise ValueError("through_message_seq must be >= 0")
        with self._workspace_lock(workspace_id):
            current = self.load_judgement_watermark(workspace_id, conversation_id, package_id)
            if through_message_seq <= current:
                return False
            path = self._workspace_dir(workspace_id) / "runtime" / "judgement_watermarks.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            payload[f"{conversation_id}:{package_id or ''}"] = through_message_seq
            self._write_json_atomic(path, payload)
            return True

    @staticmethod
    def _utc_datetime(value: datetime | None = None) -> datetime:
        current = value or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc)

    def _package_leases_file(self, workspace_id: str) -> Path:
        return self._workspace_dir(workspace_id) / "runtime" / "package_leases.json"

    def load_package_lease(self, workspace_id: str, package_id: str) -> PackageLease | None:
        leases_file = self._package_leases_file(workspace_id)
        if not leases_file.exists():
            return None
        payload = json.loads(leases_file.read_text(encoding="utf-8"))
        lease_payload = payload.get(package_id)
        return PackageLease.from_dict(lease_payload) if isinstance(lease_payload, dict) else None

    def acquire_package_lease(
        self,
        workspace_id: str,
        package_id: str,
        holder_run_id: str,
        *,
        ttl_seconds: int = 30,
        now: datetime | None = None,
    ) -> PackageLease | None:
        """抢占包级租约；冲突时返回 None，不依赖 workspace active_turn。"""

        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be >= 1")
        current = self._utc_datetime(now)
        with self._workspace_lock(workspace_id):
            existing = self.load_package_lease(workspace_id, package_id)
            if existing is not None:
                expires_at = self._utc_datetime(datetime.fromisoformat(existing.expires_at.replace("Z", "+00:00")))
                if expires_at > current and existing.holder_run_id != holder_run_id:
                    return None
                lease_id = existing.lease_id if existing.holder_run_id == holder_run_id else f"lease_{uuid4().hex[:16]}"
            else:
                lease_id = f"lease_{uuid4().hex[:16]}"
            lease = PackageLease(
                workspace_id=workspace_id,
                package_id=package_id,
                lease_id=lease_id,
                holder_run_id=holder_run_id,
                acquired_at=current.isoformat().replace("+00:00", "Z"),
                expires_at=(current + timedelta(seconds=ttl_seconds)).isoformat().replace("+00:00", "Z"),
            )
            leases_file = self._package_leases_file(workspace_id)
            leases_file.parent.mkdir(parents=True, exist_ok=True)
            payload = json.loads(leases_file.read_text(encoding="utf-8")) if leases_file.exists() else {}
            payload[package_id] = lease.to_dict()
            self._write_json_atomic(leases_file, payload)
            return lease

    def release_package_lease(
        self,
        workspace_id: str,
        package_id: str,
        lease_id: str,
        holder_run_id: str,
    ) -> bool:
        """仅允许原持有者释放租约；重复释放返回 False。"""

        with self._workspace_lock(workspace_id):
            lease = self.load_package_lease(workspace_id, package_id)
            if lease is None or lease.lease_id != lease_id or lease.holder_run_id != holder_run_id:
                return False
            leases_file = self._package_leases_file(workspace_id)
            payload = json.loads(leases_file.read_text(encoding="utf-8"))
            payload.pop(package_id, None)
            self._write_json_atomic(leases_file, payload)
            return True

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

    @staticmethod
    def _write_text_atomic(path: Path, content: str) -> None:
        """原子替换文本文件，供 JSONL 账本整批追加使用。"""

        tmp_path = path.with_name(f"{path.name}.{threading.get_ident()}.tmp")
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
