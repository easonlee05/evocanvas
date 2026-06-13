"""Evoloop 3.0 Web API 数据传输对象 (DTOs) 模块。

本模块定义了 API 接口中请求与响应的 Pydantic 数据校验模型，
包括任务创建请求、用户决策请求以及材料上传响应等。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel
except Exception:  # pragma: no cover - 允许在无 pydantic 的极简环境下通过编译检查
    class BaseModel:  # type: ignore
        """当外部未安装 pydantic 时提供一个空的兜底类。"""
        pass


class CreateTaskRequest(BaseModel):
    """任务创建请求的数据模型。

    用于定义在 Evoloop 3.0 系统中创建各种类型任务（如 manual、prd、spec_to_agent、acceptance_review）时接收的参数。
    """
    # 任务类型，例如 'prd', 'manual', 'spec_to_agent'
    type: Optional[str] = None
    # 提交该任务的用户名
    username: Optional[str] = None
    # 任务的描述性 Prompt
    prompt: Optional[str] = None
    # 任务标题
    title: Optional[str] = None
    # 任务执行的目标描述
    goal: Optional[str] = None
    # 目标特性名称
    feature: Optional[str] = None
    # 业务目标
    business_goal: Optional[str] = None
    # 业务意图（用于编译 spec）
    business_intent: Optional[str] = None
    # 模块名称
    module_name: Optional[str] = None
    # 步骤指令说明
    instructions: Optional[str] = None
    # 机器规格定义说明
    machine_spec: Optional[str] = None
    # 验收协议内容描述
    acceptance_protocol: Optional[str] = None
    # 交付实现总结
    implementation_summary: Optional[str] = None
    # 变更差异
    diff: Optional[str] = None
    # 约束条件列表
    constraints: List[str] = []
    # 偏好偏好条件列表
    preferences: List[str] = []
    # 关联材料 ID 列表
    material_ids: List[str] = []
    # 知识背景范围
    knowledge_scope: Optional[str] = None
    # 是否强制进行裁决
    force_arbitration: bool = False
    # 模型名称定义
    model: Optional[str] = None


class DecisionRequest(BaseModel):
    """用户决策/裁决请求的数据模型。

    当工作流因为 DecisionGate (裁决门禁) 而暂停时，前端通过此模型提交用户填写的决策、
    选定的选项，以及可能引用的原文片段。
    """
    # 用户提交的具体决策文本内容或理由
    decision: str
    # 用户选择的内置选项 ID
    selected_option: Optional[str] = None
    # 用户在界面上引用的相关选择片段，用于追溯证据
    quoted_selections: List[Dict[str, Any]] = []


class MaterialUploadResponse(BaseModel):
    """材料上传成功的响应模型。

    告知前端已上传材料的内部唯一 ID、处理状态以及系统提取的摘要信息。
    """
    # 唯一材料标识
    material_id: str
    # 上传状态，如 'uploaded'
    status: str
    # 材料的简要文本摘要
    summary: str

