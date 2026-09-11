"""EvoCanvas 核心契约层 Blackboard（黑板）共享内存模型。

本模块实现了一个支持动态槽位（Slot）注册、读写权限管控、类型校验与审计机制的 Blackboard（黑板）工作记忆机制，
用于在 Playbook DAG 流程中的各个步骤节点之间安全地共享上下文状态与中间交付数据。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List
from dataclasses import asdict, dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class BlackboardContext:
    """黑板槽位中存储的具体上下文切片模型。

    Attributes:
        key: 上下文切片的标识键。
        value: 上下文的具体值。
        metadata: 附带的元数据。
        owner_node: 写入或拥有该切片的节点名称或 ID。
    """
    key: str
    value: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    owner_node: str = "system"


@dataclass
class BlackboardSlot:
    """定义黑板中的一个槽位元数据，限制其支持的数据类型及读写角色白名单。

    Attributes:
        key: 槽位标识键。
        data_type: 该槽位允许存入的数据类型，支持 Union、Any 校验。
        allowed_writers: 被授权允许写入该槽位的节点/角色白名单。
        allowed_readers: 被授权允许读取该槽位的节点/角色白名单。
    """
    key: str
    data_type: Any = Any
    allowed_writers: List[str] = field(default_factory=list)
    allowed_readers: List[str] = field(default_factory=list)

    def validate_value(self, value: Any) -> None:
        """校验给定的 value 是否符合本槽位定义的数据类型约束。

        Args:
            value: 待校验的数值。

        Raises:
            TypeError: 当数据类型不匹配时抛出。
        """
        # 如果是 Any，直接放行
        if self.data_type is Any or self.data_type is None:
            return
        
        from typing import get_origin, get_args, Union
        origin = get_origin(self.data_type)
        
        # 处理 typing.Union 类型校验
        if origin is Union:
            is_valid = False
            for arg in get_args(self.data_type):
                arg_origin = get_origin(arg)
                arg_check = arg_origin if arg_origin is not None else arg
                if arg_check is Any or arg_check is None:
                    is_valid = True
                    break
                try:
                    if isinstance(value, arg_check):
                        is_valid = True
                        break
                except TypeError:
                    pass
        else:
            check_type = origin if origin is not None else self.data_type
            if check_type is Any:
                return
            
            try:
                is_valid = isinstance(value, check_type)
            except TypeError:
                is_valid = True
        
        if not is_valid:
            raise TypeError(f"Value for slot '{self.key}' must be of type {self.data_type}, got {type(value)}")


class Blackboard:
    """黑板共享状态容器，协调 DAG 各节点之间的数据传递与访问治理。"""
    def __init__(self, strict: bool = False):
        """初始化黑板容器。

        Args:
            strict: 是否启用严格模式。如果为 True，读写未预先注册的槽位将抛出错误。
        """
        self.strict = strict
        self._store: Dict[str, BlackboardContext] = {}
        self._slots: Dict[str, BlackboardSlot] = {}
        self._audit_callback = None

    def set_audit_callback(self, callback) -> None:
        """设置黑板操作的审计回调函数。

        Args:
            callback: 审计回调可执行对象。
        """
        self._audit_callback = callback

    def _audit(self, caller_id: str, action: str, key: str, success: bool, error_message: str = None) -> None:
        """触发审计回调，记录槽位读写记录。

        Args:
            caller_id: 执行操作的调用者 ID。
            action: 操作类型（如 'read', 'write'）。
            key: 操作的槽位键名。
            success: 是否操作成功。
            error_message: 失败时的详细错误描述信息。
        """
        if self._audit_callback:
            try:
                self._audit_callback(caller_id, action, key, success, error_message)
            except Exception as e:
                logger.warning(f"Failed to execute audit callback: {e}")

    def load_slots_from_dict(self, data: List[Dict[str, Any]]) -> None:
        """从字典列表中动态加载并注册多个黑板槽位元数据定义。

        Args:
            data: 包含槽位元数据（key, data_type, allowed_writers, allowed_readers）的字典列表。
        """
        type_map = {
            "int": int,
            "str": str,
            "dict": dict,
            "list": list,
            "bool": bool,
            "float": float,
            "any": Any,
            "Any": Any
        }
        for item in data:
            raw_type = item.get("data_type", "any")
            parsed_type = type_map.get(raw_type, Any) if isinstance(raw_type, str) else raw_type
            slot = BlackboardSlot(
                key=item["key"],
                data_type=parsed_type,
                allowed_writers=list(item.get("allowed_writers", [])),
                allowed_readers=list(item.get("allowed_readers", []))
            )
            self.register_slot(slot)

    def register_slot(self, slot: BlackboardSlot) -> None:
        """在黑板上注册一个槽位规格定义。

        Args:
            slot: BlackboardSlot 槽位规格实例。
        """
        self._slots[slot.key] = slot

    def write(self, key: str, value: Any, caller_id: str = None, owner_node: str = None, **metadata) -> None:
        """向黑板写入一个上下文切片，并自动进行调用者鉴权和槽位数据类型校验。

        Args:
            key: 目标槽位键名。
            value: 待写入的数据数值。
            caller_id: 发起写入调用的调用者 ID，优先级最高。
            owner_node: 写入节点名称，作为 caller_id 的次级替代。
            **metadata: 附带写入的审计元数据。

        Raises:
            KeyError: 严格模式下尝试写入未注册的键。
            PermissionError: 当调用者没有该槽位的写入权限时。
            TypeError: 当数据类型校验不通过时。
        """
        actual_caller = caller_id or owner_node or "system"
        
        try:
            # 严格模式校验键是否已注册
            if self.strict and key not in self._slots:
                raise KeyError(f"Key '{key}' is not pre-registered in strict mode")
                
            # 执行槽位权限与类型安全校验
            if key in self._slots:
                slot = self._slots[key]
                if slot.allowed_writers and actual_caller not in slot.allowed_writers:
                    raise PermissionError(f"Caller '{actual_caller}' is not authorized to write to slot '{key}'")
                slot.validate_value(value)
                
            # 执行写入存储并触发审计
            self._store[key] = BlackboardContext(key=key, value=value, metadata=metadata, owner_node=actual_caller)
            self._audit(actual_caller, "write", key, True)
        except Exception as err:
            self._audit(actual_caller, "write", key, False, str(err))
            raise

    def read(self, key: str, caller_id: str = None) -> Any:
        """从黑板读取一个上下文切片，并自动进行读取权限审计与校验。

        Args:
            key: 槽位键名。
            caller_id: 读取者的调用 ID。

        Returns:
            Any: 槽位值，若不存在则返回 None。

        Raises:
            KeyError: 严格模式下尝试读取未注册的键。
            PermissionError: 当读取者没有该槽位的读取权限时。
        """
        actual_caller = caller_id or "system"
        try:
            # 严格模式校验
            if self.strict and key not in self._slots:
                raise KeyError(f"Key '{key}' is not pre-registered in strict mode")

            # 槽位权限校验
            if key in self._slots:
                slot = self._slots[key]
                if slot.allowed_readers and actual_caller not in slot.allowed_readers:
                    raise PermissionError(f"Caller '{actual_caller}' is not authorized to read from slot '{key}'")
                    
            ctx = self._store.get(key)
            val = ctx.value if ctx else None
            self._audit(actual_caller, "read", key, True)
            return val
        except Exception as err:
            self._audit(actual_caller, "read", key, False, str(err))
            raise

    def list_keys(self) -> List[str]:
        """获取黑板中当前已写入的所有槽位键名列表。

        Returns:
            List[str]: 槽位键名列表。
        """
        return list(self._store.keys())

    def to_dict(self) -> Dict[str, Any]:
        """将黑板的存储数据扁平化转换为键值字典格式。

        Returns:
            Dict[str, Any]: 扁平的键值对字典。
        """
        return {k: v.value for k, v in self._store.items()}
