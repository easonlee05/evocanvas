"""EvoCanvas API 请求与响应模型。"""

from __future__ import annotations

from typing import List, Optional

try:
    from pydantic import BaseModel, Field, constr
except Exception:  # pragma: no cover
    class BaseModel:  # type: ignore
        pass
    def Field(default=None, **_kwargs):  # type: ignore
        return default
    def constr(**_kwargs):  # type: ignore
        return str


class CanvasMessageRequest(BaseModel):
    """画布消息提交请求。"""

    message: constr(strip_whitespace=True, min_length=1, max_length=8000)
    selected_card_ids: List[str] = Field(default_factory=list)
    material_ids: List[str] = Field(default_factory=list)
    mode: Optional[str] = None
    model: Optional[str] = None


class CanvasCardPatchRequest(BaseModel):
    """画布卡片原地修订请求，仅允许更新不改变事实边界的展示字段。"""

    title: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None


class CanvasRelationCreateRequest(BaseModel):
    """画布卡片关系创建请求，用于显性化卡片之间的语义连接。"""

    kind: str
    from_card_id: str
    to_card_id: str
    note: str = ""


class CanvasSnapshotCreateRequest(BaseModel):
    """手动创建关键状态快照的请求。"""

    title: str
    summary: str = ""


class CanvasCardMoveRequest(BaseModel):
    """卡片合法迁移请求，仅允许更新阶段归属并记录迁移原因。"""

    stage: str
    reason: str = ""
