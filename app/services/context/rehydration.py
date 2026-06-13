"""任务上下文复水引擎（Rehydration Engine）。

本模块用于扫描并解析 Prompt 提示词中包含的 "复水指针"（例如 `[需要复水: ID]`），
并从本地磁盘的缓存压实目录中加载对应的完整原始上下文数据进行动态替换，
实现长上下文在必要时的还原注入。
"""
from __future__ import annotations

import logging
import os
import re
from typing import Set

logger = logging.getLogger(__name__)


class RehydrationEngine:
    """上下文复水引擎类。

    维护压实（Compaction）缓存的本地目录，提供批量解析与动态文本替换方法。
    """

    def __init__(self, workspace_root: str):
        """初始化 RehydrationEngine 实例。

        Args:
            workspace_root: 工作空间根目录物理路径。
        """
        self.compaction_dir = os.path.join(workspace_root, "workspace", "inputs", "temp", "compaction")

    def rehydrate(self, user_content: str) -> str:
        """在用户内容中扫描 `[需要复水: ID]` 标记，并将其动态替换为本地磁盘存储的真实数据。

        如果扫描出多个复水指针，会逐个从 `workspace/inputs/temp/compaction/{ID}.txt` 中读取文本，
        并格式化为带引用边框的明细内容，替换原有的指针标记。

        Args:
            user_content: 原始待输入的文本内容。

        Returns:
            str: 完成复水注入后的完整文本内容。
        """
        if not user_content:
            return user_content

        # 正则提取所有 8 位字母数字组成的复水唯一 ID 标识，做去重处理
        rehydration_matches: Set[str] = set(re.findall(r"\[需要复水:\s*([a-zA-Z0-9]{8})\]", user_content))
        
        if not rehydration_matches:
            return user_content
            
        logger.info(f"Detected {len(rehydration_matches)} rehydration pointers.")

        rehydrated_content = user_content
        for rid in rehydration_matches:
            r_file = os.path.join(self.compaction_dir, f"{rid}.txt")
            if os.path.exists(r_file):
                try:
                    with open(r_file, "r", encoding="utf-8") as f:
                        full_text = f.read()
                    
                    # 格式化复水包裹层，注入原始上下文数据
                    injection = f"\n--- 复水明细 (引用ID: {rid}) ---\n{full_text}\n---------------------\n"
                    rehydrated_content = rehydrated_content.replace(f"[需要复水: {rid}]", injection)
                    logger.debug(f"Successfully rehydrated context {rid}")
                except Exception as e:
                    logger.error(f"Failed to read compaction file {rid}: {e}")
            else:
                logger.warning(f"Rehydration pointer {rid} references missing file.")

        return rehydrated_content

