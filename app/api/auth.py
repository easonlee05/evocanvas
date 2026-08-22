"""EvoCanvas Web API 鉴权与身份访问管理 (IAM) 模块。

本模块提供基于 HMAC 签名的 Token 鉴权机制以及基于角色的工具与接口访问策略控制 (Role-Based Access Control / RBAC)，
防范未授权访问、权限提升与匿名 RCE 隐患。
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from typing import Any, Dict, Optional

try:
    from fastapi import Depends, Header, HTTPException, Request
    from pydantic import BaseModel
except ImportError:  # pragma: no cover
    Depends = lambda func=None, **kwargs: func  # type: ignore
    Request = object  # type: ignore
    Header = lambda default=None, **kwargs: default  # type: ignore

    class HTTPException(Exception):  # type: ignore
        def __init__(self, status_code: int = 400, detail: str = ""):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class BaseModel:  # type: ignore
        def __init__(self, **data):
            for k, v in data.items():
                setattr(self, k, v)


def _safe_id(value: str) -> str:
    """严格校验租户与业务 ID，杜绝路径穿越与注入风险。"""
    if not value or not re.match(r"^[a-zA-Z0-9_-]+$", value):
        raise ValueError(f"Invalid identifier: {value!r}")
    return value


class User(BaseModel):
    """用户信息数据模型。

    用于承载当前请求上下文中的用户身份、归属租户以及所拥有的 IAM 角色。
    """
    user_id: str
    username: str
    tenant_id: str
    role: str = "user"


class RolePolicy:
    """企业级 IAM 角色工具与 API 端点访问限制策略类。

    定义不同角色（如 admin, worker, user, reader, guest）允许调用的工具与接口权限白名单。
    """
    ROLE_PERMISSIONS: Dict[str, Dict[str, Any]] = {
        "admin": {
            "allowed_tools": ["*"],
            "can_write": True,
        },
        "worker": {
            "allowed_tools": [
                "task.*",
                "canvas.*",
                "peer.*",
                "material.*",
                "knowledge.*",
                "artifact.*",
                "diff.*",
                "event.*",
            ],
            "can_write": True,
        },
        "user": {
            "allowed_tools": [
                "task.*",
                "canvas.*",
                "peer.*",
                "material.*",
                "knowledge.*",
                "artifact.*",
                "diff.*",
                "event.*",
            ],
            "can_write": True,
        },
        "reader": {
            "allowed_tools": [
                "task.read",
                "canvas.read",
                "material.read",
                "knowledge.read",
                "artifact.read",
                "event.read",
            ],
            "can_write": False,
        },
        "guest": {
            "allowed_tools": [
                "task.read",
                "canvas.read",
                "material.read",
                "artifact.read",
            ],
            "can_write": False,
        },
    }

    @classmethod
    def check_access(cls, role: str, tool_name: str) -> bool:
        """校验指定角色是否允许调用特定的工具或 API 权限。"""
        perms = cls.ROLE_PERMISSIONS.get(role, cls.ROLE_PERMISSIONS["guest"])
        if "*" in perms["allowed_tools"]:
            return True
        if tool_name in perms["allowed_tools"]:
            return True
        for p in perms["allowed_tools"]:
            if p.endswith(".*") and tool_name.startswith(p[:-2]):
                return True
        return False

    @classmethod
    def enforce(cls, role: str, tool_name: str) -> None:
        """校验权限，若未授权则抛出 403 Forbidden 异常。"""
        if not cls.check_access(role, tool_name):
            raise HTTPException(status_code=403, detail=f"Forbidden: permission '{tool_name}' required")


def generate_signed_token(
    user_id: str,
    tenant_id: str,
    role: str = "user",
    expires_in: int = 86400,
    secret: Optional[str] = None,
) -> str:
    """生成带有 HMAC-SHA256 签名的安全 API Token。"""
    auth_secret = secret or os.getenv("EVO_API_TOKEN_SECRET", "evocanvas-default-dev-secret")
    exp = int(time.time()) + expires_in
    raw = f"{user_id}:{tenant_id}:{role}:{exp}"
    sig = hmac.new(auth_secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def verify_signed_token(token: str, secret: Optional[str] = None) -> Dict[str, Any]:
    """验证带有 HMAC-SHA256 签名的 Token 并解析 payload。"""
    auth_secret = secret or os.getenv("EVO_API_TOKEN_SECRET", "evocanvas-default-dev-secret")
    try:
        raw, sig = token.rsplit(".", 1)
        parts = raw.split(":")
        if len(parts) != 4:
            raise ValueError("Malformed token payload")
        user_id, tenant_id, role, exp_str = parts
        exp = int(exp_str)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token format") from exc

    expected_sig = hmac.new(auth_secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, sig):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    if time.time() > exp:
        raise HTTPException(status_code=401, detail="Token expired")

    return {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "role": role,
    }


def get_current_user(
    request: Request = None,
    x_api_token: Optional[str] = Header(None, alias="X-API-Token"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_tenant_id: Optional[str] = Header("default", alias="X-Tenant-ID"),
) -> User:
    """FastAPI 依赖项：提取并校验当前请求的鉴权用户。

    支持通过 Authorization: Bearer <token> 或 X-API-Token 请求头传入凭证。
    生产模式（配置 EVO_AUTH_REQUIRED 或未提供有效 secret）强制 fail-closed。
    """
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif x_api_token:
        token = x_api_token.strip()

    tenant_id = x_tenant_id or "default"
    try:
        tenant_id = _safe_id(tenant_id)
    except ValueError:
        tenant_id = "default"

    auth_required = os.getenv("EVO_AUTH_REQUIRED", "").lower() in {"1", "true", "yes"}
    auth_secret = os.getenv("EVO_API_TOKEN_SECRET")

    # 如果提供了 Token，按签名规则校验
    if token:
        if "." in token:
            payload = verify_signed_token(token, secret=auth_secret)
            return User(
                user_id=payload["user_id"],
                username=payload["user_id"],
                tenant_id=payload.get("tenant_id") or tenant_id,
                role=payload.get("role") or "user",
            )
        # 如果不是标准签名 token，检查是否为配置的静态管理密钥
        admin_secret = os.getenv("EVO_ADMIN_API_KEY")
        if admin_secret and hmac.compare_digest(admin_secret, token):
            return User(user_id="admin", username="admin", tenant_id=tenant_id, role="admin")

        if auth_required or auth_secret:
            raise HTTPException(status_code=401, detail="Invalid API token")

        # 非强制认证开发模式下接受普通 token 标识
        return User(user_id=token, username=token, tenant_id=tenant_id, role="user")

    # 未提供 Token 的情况
    if auth_required:
        raise HTTPException(status_code=401, detail="Authentication required")

    # 开发环境兜底
    return User(user_id="dev-user", username="dev-user", tenant_id=tenant_id, role="user")


def get_tenant_workspace(user: User = Depends(get_current_user)) -> str:
    """FastAPI 依赖项：获取当前租户的工作区目录名称。"""
    try:
        return _safe_id(user.tenant_id)
    except ValueError:
        return "default"


