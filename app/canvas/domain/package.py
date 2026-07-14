"""EvoCanvas 结构化包（Package）与不可变包版本（PackageVersion）。

L3 规格要求：
- 一个活跃主题边界对应稳定的 package_id，结构化工作包与结构化交接物使用同一 Schema。
- 每次成功的结构化事实提交同时形成新的 state_version 与不可变 package_version。
- 包版本正文一经提交不可修改；后续确认/过时/风险标注仅追加账本事件，不回写正文。
- 区分 current_version（当前工作版本）与 latest_confirmed_version（可作正式交接依据）。

参见 docs/harness/02-memory-state/01 Memory（记忆）.md。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from app.canvas.domain.object_status import InitialGovernanceStatus


class PackageLifecycleStatus(str, Enum):
    """结构化包的生命周期状态。"""

    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass
class Package:
    """结构化包根对象，承载一个活跃主题的稳定身份与版本指针。

    一个活跃主题边界对应稳定的 package_id；跨会话同主题保持同一 package_id。
    拆分时新包记录 derived_from_package_ids，旧包不变；
    合并通过创建引用原包的新包完成，不原地拼接。
    """

    package_id: str
    workspace_id: str
    scope: Dict[str, Any] = field(default_factory=dict)
    lifecycle_status: PackageLifecycleStatus = PackageLifecycleStatus.ACTIVE
    current_version: int = 0
    latest_confirmed_version: Optional[int] = None
    state_version: int = 0
    derived_from_package_ids: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """将包根序列化为字典。"""

        data = asdict(self)
        data["lifecycle_status"] = self.lifecycle_status.value
        data["latest_confirmed_version"] = self.latest_confirmed_version
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Package":
        """从字典恢复包根实例。"""

        lifecycle_raw = data.get("lifecycle_status", PackageLifecycleStatus.ACTIVE.value)
        return cls(
            package_id=data["package_id"],
            workspace_id=data.get("workspace_id", ""),
            scope=dict(data.get("scope", {})),
            lifecycle_status=PackageLifecycleStatus(lifecycle_raw),
            current_version=int(data.get("current_version", 0)),
            latest_confirmed_version=data.get("latest_confirmed_version"),
            state_version=int(data.get("state_version", 0)),
            derived_from_package_ids=list(data.get("derived_from_package_ids", [])),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", data.get("created_at", "")),
        )


@dataclass
class PackageVersion:
    """不可变包版本，记录某一时刻受治理的对象、关系与交接模块快照。

    版本正文一经提交不可修改；后续确认、过时或风险标注仅追加账本事件，
    不回写正文，也不创建内容相同的新版本。
    """

    package_id: str
    package_version: int
    parent_version: Optional[int]
    state_version: int
    schema_version: str = "1.0"
    input_from_seq: int = 0
    input_through_seq: int = 0
    created_by_run_id: str = ""
    operation_id: str = ""
    initial_governance_status: InitialGovernanceStatus = InitialGovernanceStatus.DRAFT
    content_checksum: str = ""
    created_at: str = ""
    # 版本正文：对象图、关系、交接模块、来源引用、scope 与 background。
    # 正文只保存一份，交接模块和画布都通过对象引用或确定性投影使用它们。
    scope: Dict[str, Any] = field(default_factory=dict)
    background: Dict[str, Any] = field(default_factory=dict)
    objects: list[Dict[str, Any]] = field(default_factory=list)
    relations: list[Dict[str, Any]] = field(default_factory=list)
    handoff: Optional[Dict[str, Any]] = None
    source_refs: list[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """将不可变包版本序列化为字典。"""

        data = asdict(self)
        data["initial_governance_status"] = self.initial_governance_status.value
        data["parent_version"] = self.parent_version
        data["handoff"] = self.handoff
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PackageVersion":
        """从字典恢复不可变包版本实例。"""

        governance_raw = data.get(
            "initial_governance_status", InitialGovernanceStatus.DRAFT.value
        )
        return cls(
            package_id=data["package_id"],
            package_version=int(data["package_version"]),
            parent_version=data.get("parent_version"),
            state_version=int(data.get("state_version", 0)),
            schema_version=data.get("schema_version", "1.0"),
            input_from_seq=int(data.get("input_from_seq", 0)),
            input_through_seq=int(data.get("input_through_seq", 0)),
            created_by_run_id=data.get("created_by_run_id", ""),
            operation_id=data.get("operation_id", ""),
            initial_governance_status=InitialGovernanceStatus(governance_raw),
            content_checksum=data.get("content_checksum", ""),
            created_at=data.get("created_at", ""),
            scope=dict(data.get("scope", {})),
            background=dict(data.get("background", {})),
            objects=list(data.get("objects", [])),
            relations=list(data.get("relations", [])),
            handoff=data.get("handoff"),
            source_refs=list(data.get("source_refs", [])),
        )
