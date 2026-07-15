"""EvoCanvas 卡片关系领域模型。

L3 规格要求首版关系类型固定为：来源于、澄清了、支持、阻塞、冲突于、产出为、替代。
关系最小四元组为：起点、终点、类型、创建方式；关系 ID 与类型由系统装配。

参见 docs/harness/02-memory-state/01 Memory（记忆）.md
与 docs/harness/07-verification/01 Structure Verification（结构验证）.md。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CanvasRelationKind(str, Enum):
    """画布关系类型，对齐 L3 首版关系集合。

    replaces（替代）表达约束替代、决策重开等过时关系，是 L3 规格要求的过时留痕手段。
    """

    DERIVED_FROM = "derived_from"
    CLARIFIES = "clarifies"
    SUPPORTS = "supports"
    BLOCKS = "blocks"
    CONFLICTS_WITH = "conflicts_with"
    PRODUCES = "produces"
    REPLACES = "replaces"


@dataclass
class CanvasRelation:
    """连接两个画布对象的结构化关系。

    关系是对象图的一部分，写入时必须通过结构验证；关系本身不拥有事实裁决权。
    from_card_id / to_card_id 必须指向真实存在的对象 ID。
    """

    relation_id: str
    kind: CanvasRelationKind
    from_card_id: str
    to_card_id: str
    note: str = ""
    source_refs: List[str] = field(default_factory=list)
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将关系序列化为字典。"""

        data = asdict(self)
        data["kind"] = self.kind.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasRelation":
        """从字典恢复关系实例。

        兼容旧持久化数据：缺失的 source_refs / created_at 补默认值。
        """

        kind_raw = str(data["kind"])
        legacy_kind_mapping = {
            "reopens": CanvasRelationKind.REPLACES.value,
            "depends_on": CanvasRelationKind.BLOCKS.value,
            "relates_to": CanvasRelationKind.SUPPORTS.value,
        }
        kind_value = legacy_kind_mapping.get(kind_raw, kind_raw)
        metadata = dict(data.get("metadata", {}))
        if kind_value != kind_raw:
            metadata.setdefault("legacy_kind", kind_raw)
        return cls(
            relation_id=data["relation_id"],
            kind=CanvasRelationKind(kind_value),
            from_card_id=data["from_card_id"],
            to_card_id=data["to_card_id"],
            note=data.get("note", ""),
            source_refs=list(data.get("source_refs", [])),
            created_at=data.get("created_at", ""),
            metadata=metadata,
        )
