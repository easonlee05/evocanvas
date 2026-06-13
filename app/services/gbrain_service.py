"""基于 GBrain 命令行工具的本地经验与知识库管理服务。

本模块提供了 `GBrainKnowledge` 类，用于通过执行 `gbrain` 二进制子进程
进行本地历史知识的快速检索（`query` 与 `search` 命令）、经验与法则录入（`add` 命令）
以及自动化对抗性审查经验沉淀。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GBrainKnowledge:
    """基于 GBrain 工具链的本地知识检索与沉淀服务。

    通过外部子进程执行 `gbrain` 命令，处理格式化（JSON 或 Text）的检索返回结果，
    并支持将评审产出的缺陷自动转化为长效经验法则沉淀。
    """

    RESULT_LINE = re.compile(r"^\[(?P<score>\d+(?:\.\d+)?)\]\s+(?P<title>[^-]+?)\s+--\s+(?P<summary>.*)$")

    def __init__(self, repo_path: str, timeout_seconds: int = 5):
        """初始化 GBrainKnowledge 实例。

        Args:
            repo_path: GBrain 仓库工作的物理路径（即 cwd）。
            timeout_seconds: 执行 `gbrain` 命令的子进程超时时间，默认 5 秒。
        """
        self.repo_path = repo_path
        self.timeout_seconds = timeout_seconds

    def retrieve(self, query: str, scope: Optional[str] = None) -> Dict[str, Any]:
        """从经验库中检索相关的知识条目。

        支持自动寻找系统的 `gbrain` 路径或 Bun 全局 bin 路径。
        在执行失败或超时时提供降级策略（`degraded=True`）。

        Args:
            query: 检索关键词或语句。
            scope: 可选的作用域过滤（例如 'adversarial'）。

        Returns:
            Dict[str, Any]: 结构化的检索结果，包含 items 列表。
        """
        try:
            gbrain_bin = self._resolve_gbrain_bin()
            if not gbrain_bin:
                return self._degraded(query, scope, "gbrain binary not found")

            cmd_query = query
            if scope and scope != "default":
                cmd_query = f"[{scope}] {query}"

            errors: List[str] = []
            items: List[Dict[str, Any]] = []
            
            # 双路轮询：部分环境使用 query 另一个部分使用 search，在此做双向兼容
            for command in ("query", "search"):
                try:
                    result = subprocess.run(
                        [gbrain_bin, command, cmd_query],
                        cwd=self.repo_path,
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=self.timeout_seconds,
                    )
                except subprocess.TimeoutExpired:
                    errors.append(f"gbrain {command} timeout after {self.timeout_seconds}s")
                    continue

                if result.returncode != 0:
                    errors.append((result.stderr or f"gbrain {command} failed").strip())
                    continue

                items = self._parse_output(result.stdout)
                if items:
                    break
                errors.append(f"gbrain {command} returned no parsable results")

            if not items:
                logger.warning("Failed to parse GBrain output or no results returned")
                return self._degraded(query, scope, "; ".join(errors) or "no parsable gbrain results")

            return {
                "query": query,
                "scope": scope or "default",
                "items": items,
                "degraded": False,
            }
        except Exception as exc:
            logger.error("GBrain retrieve failed: %s", exc)
            return self._degraded(query, scope, str(exc))

    def _resolve_gbrain_bin(self) -> Optional[str]:
        """解析定位系统中的 `gbrain` 二进制文件物理路径。

        检查系统环境变量 PATH，并检查用户家目录 `.bun/bin`。

        Returns:
            Optional[str]: gbrain 的绝对路径或命令名称，若未找到则返回 None。
        """
        bun_bin = str(Path.home() / ".bun" / "bin")
        return shutil.which("gbrain") or shutil.which("gbrain", path=bun_bin)

    def _parse_output(self, stdout: str) -> List[Dict[str, Any]]:
        """解析 gbrain 的标准输出内容。

        优先尝试解析为 JSON 结构，若失败则退回到文本正则解析。

        Args:
            stdout: gbrain 进程的标准输出文本。

        Returns:
            List[Dict[str, Any]]: 解析出来的规范化知识条目列表。
        """
        json_items = self._parse_json_output(stdout)
        if json_items:
            return self._sanitize_items(json_items)
        return self._parse_text_output(stdout)

    @staticmethod
    def _parse_json_output(stdout: str) -> Optional[List[Dict[str, Any]]]:
        """尝试将输出解析为 JSON 格式的列表或结果字典。

        Args:
            stdout: gbrain 进程的标准输出文本。

        Returns:
            Optional[List[Dict[str, Any]]]: 解析成功的 JSON 对象，若非 JSON 或格式不符返回 None。
        """
        output = (stdout or "").strip()
        start_idx = -1
        for idx, char in enumerate(output):
            if char in ("{", "["):
                start_idx = idx
                break
        if start_idx < 0:
            return None
        try:
            data = json.loads(output[start_idx:])
        except json.JSONDecodeError:
            return None
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            results = data.get("results", [])
            return results if isinstance(results, list) else []
        return []

    def _parse_text_output(self, stdout: str) -> List[Dict[str, Any]]:
        """正则匹配解析非 JSON 的普通文本形式 gbrain 输出。

        限制返回的最大条目数量为 8。

        Args:
            stdout: 文本输出内容。

        Returns:
            List[Dict[str, Any]]: 提取并截断后的知识条目。
        """
        items: List[Dict[str, Any]] = []
        normalized = (stdout or "").replace("\\n", "\n")
        chunks = re.split(r"(?=^\[\d+(?:\.\d+)?\]\s)", normalized, flags=re.MULTILINE)
        for chunk in chunks:
            line = chunk.strip().splitlines()[0] if chunk.strip() else ""
            match = self.RESULT_LINE.match(line)
            if not match:
                continue
            item: Dict[str, Any] = {
                "title": match.group("title").strip()[:120],
                "summary": match.group("summary").strip()[:400],
            }
            try:
                item["score"] = float(match.group("score"))
            except ValueError:
                pass
            items.append(item)
            if len(items) >= 8:
                break
        return items

    @staticmethod
    def _sanitize_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """对解析出来的条目进行字段清洗与字数截断安全处理。

        截断标题在 120 字符以内，摘要在 400 字符以内，只保留最多 8 条。

        Args:
            items: 待清洗的原始字典列表。

        Returns:
            List[Dict[str, Any]]: 格式化后安全的列表。
        """
        safe_items: List[Dict[str, Any]] = []
        for item in items[:8]:
            if not isinstance(item, dict):
                continue
            safe: Dict[str, Any] = {}
            title = item.get("title") or item.get("name") or "未命名知识"
            summary = item.get("summary") or item.get("snippet") or item.get("excerpt") or ""
            if isinstance(title, str):
                safe["title"] = title[:120]
            if isinstance(summary, str):
                safe["summary"] = summary[:400]
            score = item.get("score")
            if isinstance(score, (int, float)):
                safe["score"] = score
            if safe:
                safe_items.append(safe)
        return safe_items

    @staticmethod
    def _degraded(query: str, scope: Optional[str], error: str) -> Dict[str, Any]:
        """构造降级返回的结果字典。

        Args:
            query: 检索的关键词。
            scope: 检索范围。
            error: 降级发生的原因/错误详情。

        Returns:
            Dict[str, Any]: degraded 标志为 True 且 items 为空的检索结果。
        """
        return {
            "query": query,
            "scope": scope or "default",
            "degraded": True,
            "items": [],
            "error": error,
        }

    def learn(self, title: str, summary: str, scope: Optional[str] = None) -> bool:
        """将新的经验/规则持久化写入 GBrain 经验库。

        Args:
            title: 经验条目的标题。
            summary: 经验的详细描述或规则。
            scope: 录入的作用域分区（例如 'adversarial'）。

        Returns:
            bool: 写入是否成功。
        """
        try:
            gbrain_bin = self._resolve_gbrain_bin()
            if not gbrain_bin:
                logger.warning("gbrain binary not found, skipping learning.")
                return False

            cmd = [gbrain_bin, "add", "--title", title, "--summary", summary]
            if scope:
                cmd.extend(["--scope", scope])
                
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
            )
            if result.returncode != 0:
                logger.error(f"GBrain learn failed: {result.stderr}")
                return False
            return True
        except Exception as exc:
            logger.error(f"GBrain learn exception: {exc}")
            return False

    def learn_from_review(self, review_result: Any) -> int:
        """从验收审查结果中提取 issues 并转化为对抗性经验写入 GBrain。

        Args:
            review_result: 包含 issues 列表的审查结果对象。

        Returns:
            int: 成功录入的经验数量。
        """
        count = 0
        for issue in getattr(review_result, "issues", []):
            title = f"Adversarial Review Finding: {issue.summary}"
            summary = f"Rule derived from failed review: {issue.recommendation}. Relates to: {', '.join(issue.related_requirement_ids)}"
            if self.learn(title, summary, scope="adversarial"):
                count += 1
        return count

