"""用户安全产物与材料文件的外观服务（Facade）。

本服务模块为系统中的产物与材料文件读写操作提供统一的安全入口，
底层通过底座存储层（Storage Port/Adapter）实现落盘与读取。
"""
from __future__ import annotations

from typing import Any


class FileService:
    """产物与材料文件管理外观服务类。

    提供对任务关联产物（Artifact）的创建、读取、列表获取与自动备份管理。
    """

    def __init__(self, storage: Any):
        """初始化 FileService 实例。

        Args:
            storage: 底层数据持久化的 Storage 存储适配器实例。
        """
        self.storage = storage

    def write_artifact(self, task_id: str, name: str, content: str, created_by: str = "Writer"):
        """为指定任务写入/生成一个新的产物（Artifact）。

        Args:
            task_id: 关联的任务 ID。
            name: 产物的文件名。
            content: 产物的详细内容。
            created_by: 创建产物的角色标识，默认为 "Writer"。

        Returns:
            Artifact: 成功生成的产物实体对象。
        """
        return self.storage.write_artifact(task_id=task_id, name=name, content=content, created_by=created_by)

    def read_artifact(self, artifact_id: str):
        """读取指定产物 ID 的详细内容与元数据。

        Args:
            artifact_id: 产物唯一标识符。

        Returns:
            Artifact: 产物实体。
        """
        return self.storage.read_artifact(artifact_id)

    def list_artifacts(self, task_id: str):
        """列出指定任务 ID 关联的所有产物（Artifacts）列表。

        Args:
            task_id: 任务的唯一标识。

        Returns:
            List[Artifact]: 产物对象列表。
        """
        return self.storage.list_artifacts(task_id)

    def backup_artifact(self, artifact_id: str):
        """在修改前为指定产物创建历史备份。

        Args:
            artifact_id: 待备份的产物 ID。

        Returns:
            Dict[str, Any]: 包含备份详情（如 backup_id）的字典。
        """
        return self.storage.backup_artifact(artifact_id)

