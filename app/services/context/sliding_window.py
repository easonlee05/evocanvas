"""基于级联压实（Cascading Compaction）的工业级滑动窗口上下文管理器。

本模块提供了一个大模型上下文管理机制：当历史会话所占用的 Token 额度超出预设阈值时，
自动对历史消息触发“脱水式级联压实”。脱水原文被持久化至本地缓存目录中，
从而在满足大模型上下文长度限制的同时，为下游“复水”引擎提供数据支撑。
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Tuple
from uuid import uuid4

from app.services.context.token_counter import TokenCounter

logger = logging.getLogger(__name__)


class SlidingWindow:
    """级联压实滑动窗口上下文管理器类。

    提供 Token 预估计算、超出阈值时的级联脱水、以及文件落盘管理等能力。
    """

    def __init__(self, workspace_root: str, max_tokens: int = 4096, soft_limit_ratio: float = 0.8):
        """初始化 SlidingWindow 实例。

        Args:
            workspace_root: 工作空间物理根路径。
            max_tokens: 上下文支持的最大 Token 数量，默认 4096。
            soft_limit_ratio: 触发压缩的软性占比阈值，默认 0.8（即 max_tokens 的 80%）。
        """
        self.workspace_root = workspace_root
        self.max_tokens = max_tokens
        self.soft_limit_tokens = int(max_tokens * soft_limit_ratio)
        self.counter = TokenCounter()
        self.compaction_dir = os.path.join(workspace_root, "workspace", "inputs", "temp", "compaction")
        os.makedirs(self.compaction_dir, exist_ok=True)

    def _persist_to_disk(self, content: str) -> str:
        """将脱水的原始详细长文本写入本地压实目录，并生成唯一的 8 位引用 ID。

        Args:
            content: 脱水消息的原始全文。

        Returns:
            str: 用于后续复水的 8 位 UUID 标识符。
        """
        compaction_id = uuid4().hex[:8]
        compaction_file = os.path.join(self.compaction_dir, f"{compaction_id}.txt")
        try:
            with open(compaction_file, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Failed to persist compaction: {e}")
        return compaction_id

    def compact(self, history: List[Dict[str, Any]]) -> Tuple[str, int]:
        """处理会话历史，在总 Token 超出软阈值时，对较早的信息触发脱水级联压实。

        策略：
        - 倒序评估或保留：保证最近 2 个回合（最近的消息）不进行脱水，以维持近期的对话连贯性；
        - 对早于近 2 回合且长度较长（超过 300 字符）的历史消息，将其原始文本持久化到本地，
          并替换为简略的摘要及复水 ID 标记，进而减少总体 Token 消耗。

        Args:
            history: 会话历史列表，每条历史为包含 role 和 content 的字典。

        Returns:
            Tuple[str, int]: 返回压实完成后的历史提示文本，以及本次触发的脱水次数。
        """
        processed_history = []
        total_tokens = 0
        compactions = 0

        # 首先预先计算每一条消息占用的 Token 数量并进行累加
        msg_tokens = []
        for msg in history:
            content = msg.get("content", "")
            tks = self.counter.count(content)
            msg_tokens.append({"role": msg.get("role", "unknown"), "content": content, "tokens": tks})
            total_tokens += tks

        if total_tokens <= self.soft_limit_tokens:
            # 未超出软限阈值，直接进行格式化拼接输出，无需压缩
            history_str = ""
            for msg in msg_tokens:
                history_str += f"【{msg['role']}】:\n{msg['content']}\n\n"
            return history_str, compactions

        logger.info(f"Token soft limit reached ({total_tokens} > {self.soft_limit_tokens}). Triggering compaction.")

        # 级联压实逻辑：
        # 依次从旧到新遍历历史会话。当累积的 Token 超出软限制且该消息不属于最近 2 个回合时，
        # 如果长度大于 300 字符则触发脱水持久化，将内容精简为摘要。
        history_str = ""
        current_cumulative_tokens = total_tokens
        
        for i, msg in enumerate(msg_tokens):
            role = msg['role']
            content = msg['content']
            tks = msg['tokens']

            # 判断是否是最近 2 条消息，如果是，则强制保留不脱水
            is_recent = (i >= len(msg_tokens) - 2)
            needs_compaction = (current_cumulative_tokens > self.soft_limit_tokens) and not is_recent

            if needs_compaction and tks > 300:  # 仅对存在实质压缩空间的非空/非极短消息进行脱水
                compaction_id = self._persist_to_disk(content)
                # 精炼摘要：保留头尾各 150 字符，并在中间注入复水标识符
                summary = content[:150] + f"\n... [长文本已触发脱水，原文本引用 ID: {compaction_id}] ...\n" + content[-150:]
                
                new_tks = self.counter.count(summary)
                current_cumulative_tokens -= (tks - new_tks)
                compactions += 1
                history_str += f"【{role}】:\n{summary}\n\n"
            else:
                history_str += f"【{role}】:\n{content}\n\n"

        return history_str, compactions
