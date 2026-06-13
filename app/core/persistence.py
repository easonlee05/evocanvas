"""Evoloop 3.0 核心契约层文件持久化混入类定义。

本模块提供了一个通用的文件持久化混入类（FilePersistenceMixin），
支持自动识别文件扩展名（JSON/YAML）并进行结构化序列化与反序列化。
"""
from __future__ import annotations

import json
from typing import Any, Dict, Type, TypeVar
import yaml

from app.core.errors import DomainError

T = TypeVar("T", bound="FilePersistenceMixin")


class FilePersistenceMixin:
    """提供统一的 JSON/YAML 文件读取和存储能力的混入类。

    该类通过 self.to_dict() 与 cls.from_dict(data) 接口，实现通用的序列化和持久化逻辑。
    """

    def save_to_file(self, file_path: str) -> None:
        """根据文件路径的后缀自动将契约实例以 JSON 或 YAML 格式保存至本地磁盘。

        Args:
            file_path: 保存的目标文件绝对或相对路径。

        Raises:
            DomainError: 当序列化或写入文件失败时，抛出 'persistence.save_failed' 错误。
        """
        try:
            # 获取当前对象的字典形式
            data = self.to_dict()
            # 区分 yaml 与 json
            if file_path.endswith((".yaml", ".yml")):
                with open(file_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
            else:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise DomainError(
                code="persistence.save_failed",
                message=f"Failed to save to {file_path}: {str(e)}"
            ) from e

    @classmethod
    def load_from_file(cls: Type[T], file_path: str) -> T:
        """根据文件路径的后缀自动从 JSON 或 YAML 文件反序列化加载契约实例。

        Args:
            file_path: 目标文件的数据源路径。

        Returns:
            T: 反序列化还原后的契约实例对象。

        Raises:
            DomainError: 当读取、解析文件，或实例化失败时，抛出 'persistence.load_failed' 错误。
        """
        try:
            # 区分 yaml 与 json
            if file_path.endswith((".yaml", ".yml")):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
        except Exception as e:
            raise DomainError(
                code="persistence.load_failed",
                message=f"Failed to load from {file_path}: {str(e)}"
            ) from e

        try:
            # 通过类方法 from_dict 实例化
            return cls.from_dict(data)
        except Exception as e:
            raise DomainError(
                code="persistence.load_failed",
                message=f"Failed to instantiate {cls.__name__} from data: {str(e)}"
            ) from e
