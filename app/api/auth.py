"""Evoloop 3.0 Web API 鉴权与身份访问管理 (IAM) 依赖模块。

本模块提供轻量级的 Token 鉴权以及基于角色的工具访问策略控制 (Role-Based Tool Policy Control)，
以满足 Evoloop 3.0 对 Agent 调用能力的受控限制规范。
"""
from typing import Optional
from fastapi import Header, Depends
from pydantic import BaseModel

class User(BaseModel):
    """用户信息数据模型。

    用于承载当前请求上下文中的用户身份、归属租户以及所拥有的 IAM 角色。
    """
    user_id: str
    username: str
    tenant_id: str
    role: str = "user"

class RolePolicy:
    """企业级 IAM 角色工具与路径限制策略类。

    该类定义了不同角色（如 admin, worker, reader, guest）允许调用的工具白名单
    以及是否具备写入权限。生命周期为静态单例。
    """
    ROLE_PERMISSIONS = {
        "admin": {"allowed_tools": ["*"], "can_write": True},
        "worker": {"allowed_tools": ["artifact.*", "material.*", "knowledge.*", "diff.*", "event.*"], "can_write": True},
        "reader": {"allowed_tools": ["material.read", "knowledge.retrieve", "artifact.read"], "can_write": False},
        "guest": {"allowed_tools": ["artifact.read"], "can_write": False},
    }

    @classmethod
    def check_access(cls, role: str, tool_name: str) -> bool:
        """校验指定角色是否允许调用特定的工具。

        Args:
            role (str): 用户角色名称（例如 'admin', 'worker', 'reader', 'guest'）。
            tool_name (str): 需要调用的工具全称（例如 'artifact.write'）。

        Returns:
            bool: 如果允许调用返回 True，否则返回 False。
        """
        perms = cls.ROLE_PERMISSIONS.get(role, cls.ROLE_PERMISSIONS["guest"])
        # 管理员默认拥有所有工具权限
        if "*" in perms["allowed_tools"]:
            return True
        # 精确匹配工具白名单
        if tool_name in perms["allowed_tools"]:
            return True
        # 通配符前缀匹配，例如匹配 "artifact.*"
        for p in perms["allowed_tools"]:
            if p.endswith(".*") and tool_name.startswith(p[:-2]):
                return True
        return False

def get_current_user(
    x_api_token: Optional[str] = Header(None, alias="X-API-Token"),
    x_tenant_id: Optional[str] = Header("default", alias="X-Tenant-ID")
) -> User:
    """FastAPI 依赖项：获取当前请求的鉴权用户。

    使用 HTTP Header 中的 X-API-Token 进行轻量级校验，如果未提供，
    则降级为匿名访客身份，以维持向后兼容性。

    Args:
        x_api_token (Optional[str]): 请求头中的 API 访问凭证，默认为 None。
        x_tenant_id (Optional[str]): 租户标识，默认为 "default"。

    Returns:
        User: 鉴权通过后的 User 对象。
    """
    # 模拟管理员 Token 校验
    if x_api_token == "test-admin-token":
        return User(user_id="admin-01", username="admin", tenant_id=x_tenant_id, role="admin")
    elif x_api_token:
        # 普通携带 token 的用户
        return User(user_id=x_api_token, username=x_api_token, tenant_id=x_tenant_id, role="user")
    
    # 匿名兜底 guest 身份
    return User(user_id="anonymous", username="anonymous", tenant_id=x_tenant_id, role="guest")

def get_tenant_workspace(user: User = Depends(get_current_user)) -> str:
    """FastAPI 依赖项：获取当前租户的工作区目录名称。

    校验租户 ID 是否符合安全规范（仅允许字母数字、中划线和下划线），
    以防范潜在的路径穿越 (Path Traversal) 安全漏洞。

    Args:
        user (User): 当前鉴权通过的用户对象。

    Returns:
        str: 安全校验后的租户工作区目录名。如果校验未通过则返回 "default"。
    """
    # 强制执行安全的租户 ID 正则过滤以防范路径穿越风险
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', user.tenant_id):
        return "default"
    return user.tenant_id

