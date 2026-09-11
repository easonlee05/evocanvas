"""EvoCanvas API 请求与响应模型。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, ConfigDict, Field, constr
except Exception:  # pragma: no cover
    class BaseModel:  # type: ignore
        pass
    def Field(default=None, **_kwargs):  # type: ignore
        return default
    def constr(**_kwargs):  # type: ignore
        return str
    ConfigDict = None  # type: ignore


class CanvasMessageRequest(BaseModel):
    """画布消息提交请求。"""

    submission_id: Optional[str] = Field(default=None, min_length=1, max_length=128)

    message: constr(strip_whitespace=True, min_length=1, max_length=8000)
    selected_card_ids: List[str] = Field(default_factory=list)
    material_ids: List[str] = Field(default_factory=list)
    source_ref_ids: List[str] = Field(default_factory=list)
    mode: Optional[str] = None
    model: Optional[str] = None
    # 浏览器本机设置中临时传入的 Provider 配置；不写入画布事实或消息正文。
    llm_config: Optional[Dict[str, str]] = None


class CanvasCardPatchRequest(BaseModel):
    """画布卡片原地修订请求，仅允许更新不改变事实边界的展示字段。"""

    if ConfigDict is not None:
        model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[List[str]] = None


class CanvasCardCreateRequest(BaseModel):
    """画布卡片新建请求，仅承载展示字段。

    L3 规格：kind 必须是五类合法枚举之一；status 由后端按类型默认值写入，
    不允许调用方传入；stage 字段已下线，不再接受。
    metadata 仅承载展示辅助信息（如 section_hint），不写入业务状态。
    """

    if ConfigDict is not None:
        model_config = ConfigDict(extra="forbid")

    kind: str
    title: constr(strip_whitespace=True, min_length=1, max_length=200)
    summary: str = ""
    tags: Optional[List[str]] = None
    source_refs: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class CanvasRelationCreateRequest(BaseModel):
    """画布卡片关系创建请求，用于显性化卡片之间的语义连接。"""

    kind: str
    from_card_id: str
    to_card_id: str
    note: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CanvasSnapshotCreateRequest(BaseModel):
    """手动创建关键状态快照的请求。"""

    title: str
    summary: str = ""


class CanvasCardMoveRequest(BaseModel):
    """卡片合法迁移请求，仅允许更新阶段归属并记录迁移原因。"""

    stage: str
    reason: str = ""
