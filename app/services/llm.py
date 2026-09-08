"""Real LLM implementation using OpenAI compatible API."""
import json
import os
import time
import urllib.request
from typing import Any, Callable, Dict, Optional, Tuple, List
from urllib.parse import urlparse
from uuid import uuid4

from app.core.ports import LLMResult

TelemetryCallback = Callable[[str, Dict[str, Any]], None]


class OpenAILLM:
    """OpenAI 兼容的大语言模型（LLM）请求服务类。

    封装了与外部 LLM 网关的交互逻辑，支持同步非流式与生成器流式请求，
    并内置上下文滑动窗口缩减、动态知识水合 (Rehydration) 以及多模型 Fallback 容灾策略。

    生命周期：
        通常为单例，在服务启动时传入配置的 API Key 和 Base URL 初始化。
    """

    WRITER_MAX_TOKENS = 24000
    DEFAULT_MAX_TOKENS = 4096

    def __init__(self, api_key: str, base_url: str):
        """初始化 OpenAILLM 实例。"""
        import sys
        is_testing = any("unittest" in arg or "pytest" in arg for arg in sys.argv) or "tests" in sys.modules or "unittest" in sys.modules
        if is_testing:
            self.api_key = ""
        else:
            self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _host(self) -> str:
        """获取 base_url 中的主机名部分，用于遥测记录。

        Returns:
            str: 主机名。
        """
        return urlparse(self.base_url).netloc or self.base_url

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        """计算从开始时间戳到当前时间的毫秒数。

        Args:
            started_at: 开始的时间戳（基于 time.monotonic()）。

        Returns:
            int: 毫秒数。
        """
        return max(0, int((time.monotonic() - started_at) * 1000))

    @staticmethod
    def _emit(telemetry: Optional[TelemetryCallback], event_type: str, payload: Dict[str, Any]) -> None:
        """触发遥测日志回调，发送结构化事件。"""
        if telemetry:
            try:
                telemetry(event_type, payload)
            except Exception:
                pass
        
        # 本地控制台高亮输出，记录 LLM 各阶段用时与 Token 消耗
        import logging
        logger = logging.getLogger("llm.telemetry")
        
        if event_type == "llm.call.started":
            model = payload.get("model", "unknown")
            stream = payload.get("stream", False)
            logger.info(f"[LLM Telemetry] Started. Model: {model} | Stream: {stream}")
            
        elif event_type == "llm.call.headers_received":
            model = payload.get("model", "unknown")
            ttfb = payload.get("ttfb_ms", 0)
            logger.info(f"[LLM Telemetry] TTFB: {ttfb}ms | Model: {model}")
            
        elif event_type == "llm.call.completed":
            duration = payload.get("duration_ms", 0)
            model = payload.get("model", "unknown")
            prompt_tokens = payload.get("prompt_tokens")
            completion_tokens = payload.get("completion_tokens")
            total_tokens = payload.get("total_tokens")
            
            # 如果是 None，则进行估算，防止某些特殊情况下为 None
            if prompt_tokens is None:
                prompt_tokens = 0
            if completion_tokens is None:
                output_chars = payload.get("output_chars", 0)
                completion_tokens = int(output_chars / 2) if output_chars else 0
            if total_tokens is None:
                total_tokens = prompt_tokens + completion_tokens
                
            logger.info(
                f"[LLM Telemetry] Completed. Model: {model} | Duration: {duration}ms | "
                f"Prompt Tokens: {prompt_tokens} | Completion Tokens: {completion_tokens} | Total: {total_tokens}"
            )
            print(
                f"\n\033[92m[LLM Telemetry] Model: {model} | 阶段总耗时: {duration}ms | "
                f"输入 Tokens: {prompt_tokens} | 输出 Tokens: {completion_tokens} | "
                f"总消耗 Tokens: {total_tokens}\033[0m\n", flush=True
            )
            
        elif event_type == "llm.call.failed":
            duration = payload.get("duration_ms", 0)
            model = payload.get("model", "unknown")
            err = payload.get("error_type", "UnknownError")
            logger.error(f"[LLM Telemetry] Failed. Model: {model} | Duration: {duration}ms | Error: {err}")
            print(
                f"\n\033[91m[LLM Telemetry] Model: {model} | 调用失败 | "
                f"耗时: {duration}ms | 错误类型: {err}\033[0m\n", flush=True
            )

    @classmethod
    def _max_tokens_for_role(cls, role: str) -> int:
        """根据代理角色返回最大允许的 Token 限制数。

        如果是 writer 角色则给予更大的 Token 窗口，其余角色给予默认窗口。

        Args:
            role: 代理角色的名称（例如 writer, pm, qa 等）。

        Returns:
            int: 最大 Token 限制。
        """
        return cls.WRITER_MAX_TOKENS if role.lower() == "writer" else cls.DEFAULT_MAX_TOKENS

    # ── 兼容层的全局系统提示（Legacy System Prompt）────────────────
    # 本兼容层保留旧实现；现行边界以 docs/harness/01-instructions-context/ 为准。
    _SYSTEM_BASE = """你是 EvoCanvas 的协作引擎，一个面向产品经理的结构化工作助手。

# 核心原则

- 默认帮助用户看清问题、边界与选项，而不是替用户越权拍板。
- 透明优先：先暴露不确定性，再沉淀约束，再形成待决策，最后生成交接物。
- 不静默合并：当输入之间存在冲突、歧义或上下文缺失时，必须显性化冲突，不得假装已经形成稳定结论。
- 不伪装确定性：草稿不得写得像结论，待澄清项不得写得像已解决问题，待决策候选不得写得像已拍板结果。
- 高风险内容不得自行宣布生效。

# 行为约束

- ALWAYS 在输出中区分「已确认事实」与「当前理解/草稿」。
- ALWAYS 当信息不足时给出可推进草稿，但必须显式标注边界和置信度。
- NEVER 在未经用户确认的情况下，将多个矛盾输入合并为单一结论。
- NEVER 用「已完成」「已确认」等措辞描述尚未通过验证的内容。
- NEVER 跳过澄清步骤直接输出最终交付物。
- 当你的判断依据不足时，使用「基于当前信息，我倾向于…但需要确认」而非断言式表述。

# 工具使用策略

你可以使用以下领域工具，按场景选择：
- 需要理解用户上传的材料时：先 `material.read`（获取摘要），再 `material.parse`（结构化解析）。
- 需要查找已有知识或历史决策时：使用 `knowledge.retrieve`。
- 需要写入或更新交付产物时：使用 `artifact.write`（自动版本管理）。写入前可用 `artifact.read` 检查已有内容。
- 需要校验格式合规性时：使用 `format.validate`。
- 需要从变更差异中提取规则候选时：使用 `diff.extract_rules`。
- 不要在一次步骤中调用同一工具超过 5 次。如果需要批量操作，先规划再执行。

# 上下文管理

- 对话历史可能因长度被压缩。如果你看到历史中出现脱水标记或摘要，请基于摘要继续推理，不要要求用户重复已说过的内容。
- 全局锁定上下文（Sticky Latch）中的规则拥有最高优先级，不可被后续对话覆盖。

# 输出格式

- 使用 Markdown 格式，结构清晰度应与任务复杂度匹配。
- 简单回应通常 1-2 段即可，不需要列表或标题。
- 不使用嵌套列表；复杂结构尽量扁平化，确保用户能快速扫描。
- 对于结构化输出（证据卡、澄清卡、约束卡等），每个卡片应包含：来源、内容、置信度。
- 不要以「好的」「明白了」「收到」开头，直接进入实质内容。
- 不要在输出中使用 emoji，除非用户明确要求。
"""

    # ── 兼容层的角色提示（Legacy Role Prompts）────────────────────
    # 现行架构不采用 Stage Prompt；阶段与治理由 Runtime、Skills 和工具约束负责。
    _ROLE_PROMPTS = {
        "compiler": """
# 当前角色：规范编译器 (Compiler)

你的职责是将非结构化的业务意图进行标准化解析，提取证据、识别歧义、标注冲突。

## 本轮行为边界
- 允许：探索性提取、术语标准化、证据卡生成、问题定义卡生成。
- 禁止：跳过提取直接生成最终文档、将草稿标记为已确认。
- 主对象：证据卡 (evidence)、问题定义卡 (problem)。

## 输出要求
- 每个提取结果必须标注来源片段和置信度（高/中/低）。
- 当发现矛盾输入时，必须生成待澄清卡而非静默取舍。
- 如果材料信息密度过低，明确告知用户需要补充什么。
""",
        "inputcompiler": """
# 当前角色：输入编译器 (InputCompiler)

你的职责是接收新的非结构化输入，将其编译为可被后续阶段消费的证据与问题定义。

## 本轮行为边界
- 允许：提取关键信息、生成证据卡、标记信息缺口、识别潜在冲突。
- 禁止：跳过提取直接给出结论、将未验证的理解标记为已确认。
- 主对象：证据卡 (evidence)、问题定义卡 (problem)。

## 输出要求
- 本轮形成内容、未决边界、建议下一步。
- 每个提取项必须标注来源与置信度。
- 遇到信息不足时，明确列出需要用户补充的材料。
""",
        "clarifier": """
# 当前角色：澄清推进员 (Clarifier)

你的职责是显性化歧义、缺口与冲突，优先推动待澄清而不是抢结论。

## 本轮行为边界
- 允许：追问、标注冲突、生成待澄清卡、更新卡片摘要。
- 禁止：在用户未确认前把歧义合并为单一结论。
- 主对象：待澄清卡 (clarification)。

## 输出要求
- 待澄清项至少说明：歧义点、影响范围、建议的澄清方向。
- 本轮形成内容、未决与冲突、对象状态、建议下一步。
- 当存在多个等价解释时，列出选项并说明需要用户做何取舍。
""",
        "optionbuilder": """
# 当前角色：方案构建员 (OptionBuilder)

你的职责是接收方案建议并生成可比选项，帮助用户看到取舍空间。

## 本轮行为边界
- 允许：整理方案候选、列出关键差异、标注适用条件。
- 禁止：在用户未拍板前宣布某一方案已确定。
- 主对象：方案候选卡 (option)。

## 输出要求
- 默认先给可比选项，不主动替用户拍板。
- 如果给出推荐，必须单列“推荐理由”，并说明推荐所依赖的假设。
- 每个选项应包含：适用场景、主要收益、主要风险、需要进一步确认的问题。
""",
        "handoffbuilder": """
# 当前角色：交接收束员 (HandoffBuilder)

你的职责是收束当前结构化交接物，同时保留未解决缺口与风险边界。

## 本轮行为边界
- 允许：整理已确认内容、高亮未决边界、生成交接草稿。
- 禁止：为了文档完整感吞掉未确认风险、把草稿包装成最终结论。
- 主对象：结构化交接物 (handoff)。

## 输出要求
- 结构化交接物至少区分：已确认事实、高价值但未确认的草稿、已知风险与后续跟进项。
- 高价值但未确认的草稿必须保持可见，并标注“待确认”。
- 交接物的可读性不能凌驾于真实性之上。
""",
        "reviewer": """
# 当前角色：验收评审器 (Reviewer)

你的职责是对比需求规格，评审产物与规格的一致性，发现覆盖缺口和风险。

## 本轮行为边界
- 允许：需求覆盖度检查、变更影响分析、安全审计、评审结论输出。
- 禁止：修改原始规格、宣布评审通过（这需要人工确认）。
- 主对象：评审结果 (review_result)。

## 输出要求
- 按严重程度排序发现项：阻塞性 > 风险性 > 建议性。
- 每个发现项必须包含：涉及位置、规格依据、影响范围。
- 如果没有发现问题，明确声明并指出残余风险。
""",
        "writer": """
# 当前角色：产物写入器 (Writer)

你的职责是将编译或评审结论按标准格式写入交付资产。

## 本轮行为边界
- 允许：格式化写入、版本管理、内容整合、文档结构优化。
- 禁止：自行补充上游未给出的事实判断、修改已确认的约束内容。
- 主对象：machine_spec、human_brief、review_result 等交付物。

## 输出要求
- 你有更大的输出空间（24K tokens），可用于完整文档输出。
- 写入内容必须严格忠实于上游结论，不得在整理过程中偷改地位。
- 当上游结论存在不稳定内容时，必须在文档中标注而非消化掉。
""",
    }

    def _build_prompts(self, role: str, prompt: str, context: Dict[str, Any], is_stream: bool = False) -> Tuple[str, List[Dict[str, str]], str]:
        """构建兼容 LLM 服务请求所需的提示结构。

        流程包括：
        1. 拼接兼容层的全局系统提示（全局原则 + 行为约束 + 工具策略）；
        2. 拼接 Role-Specific Prompt（角色行为边界 + 输出要求）；
        3. 注入 Sticky Latch 全局锁定上下文；
        4. 对历史对话列表应用 Sliding Window（滑动窗口）压缩；
        5. 处理动态的用户 Prompt、追加上下文水合（Rehydration）；
        6. 生成 OpenAI 与 Anthropic 兼容的消息结构。

        Args:
            role: 执行任务的代理角色名称。
            prompt: 用户的当前提示词或具体指令。
            context: 任务关联的上下文，包含 title, goal, round_history 等。
            is_stream: 是否是流式调用。

        Returns:
            Tuple[str, List[Dict[str, str]], str]:
                - system_prompt (系统提示词字符串)
                - messages (符合 OpenAI 规范的 messages 列表)
                - anthropic_user_prompt (适用于 Anthropic 的用户提示词)
        """
        import os
        from app.services.context.sliding_window import SlidingWindow
        from app.services.context.rehydration import RehydrationEngine

        title = context.get("title") or "未命名任务"
        goal = context.get("goal") or "无特定目标"
        workspace_root = os.getcwd()

        # ── 1. 拼接 System Prompt：Base + Role ──────────────
        system_prompt = self._SYSTEM_BASE
        role_prompt = self._ROLE_PROMPTS.get(role.lower(), f"\n# 当前角色：{role}\n你是一个专业协作角色，请根据任务目标提供高质量的输出。\n")
        system_prompt += role_prompt

        # ── 2. Sticky Latch：全局锁定上下文 ─────────────────
        memory_path = os.path.join(workspace_root, "MEMORY.md")
        claude_path = os.path.join(workspace_root, "CLAUDE.md")
        fixed_context = ""
        for path, name in [(memory_path, "MEMORY.md"), (claude_path, "CLAUDE.md")]:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            fixed_context += f"\n--- {name} (不可变全局规则，最高优先级) ---\n{content}\n"
                except Exception:
                    pass
        if fixed_context:
            system_prompt += f"\n# 全局锁定上下文 (Sticky Latch)\n以下规则拥有最高优先级，不可被后续对话覆盖：\n{fixed_context}"

        # ── 3. 流式模式下的额外输出精简指令 ──────────────────
        if is_stream and role.lower() != "writer":
            system_prompt += "\n# 流式输出指令\n当前为实时对话模式。每次输出尽量控制在 2 段内，优先给出关键判断。输出必须包含：本轮形成内容、未决边界、建议下一步。"

        # ── 4. Context Management: 滑动窗口压缩对话历史 ─────
        window_mgr = SlidingWindow(workspace_root=workspace_root, max_tokens=self._max_tokens_for_role(role))
        history_str, compactions = window_mgr.compact(context.get("round_history", []))
        if compactions > 0:
            self._emit(None, "llm.context.compacted", {"call_id": context.get("task_id", ""), "compactions": compactions})

        # ── 5. 拼接 User Prompt：动态任务信息 + 历史 + 当前输入
        dynamic_task_info = f"<task_context>\n任务标题: {title}\n任务目标: {goal}\n当前角色: {role}\n</task_context>\n\n"
        combined_user_content = dynamic_task_info

        if history_str:
            combined_user_content += f"<conversation_history>\n{history_str}\n</conversation_history>\n\n请基于上述历史继续你的工作。\n\n"

        combined_user_content += prompt or f"请开始处理任务: {title}"

        # ── 6. Rehydration：动态还原被脱水的上下文引用 ───────
        rehydrator = RehydrationEngine(workspace_root=workspace_root)
        combined_user_content = rehydrator.rehydrate(combined_user_content)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": combined_user_content}
        ]

        anthropic_user_prompt = combined_user_content

        return system_prompt, messages, anthropic_user_prompt

    def invoke(self, role: str, prompt: str, context: Dict[str, Any]) -> LLMResult:
        """执行同步的非流式 LLM 请求。

        支持在遇到特定格式不支持错误时重试 Anthropic 格式，或在发生 Vip 限制/故障时无缝降级至备用模型（如 DeepSeek-V3）。

        Args:
            role: 执行任务的代理角色。
            prompt: 用户的当前提示词或具体指令。
            context: 任务关联的上下文环境参数。

        Returns:
            LLMResult: 包含生成内容与元数据的 LLM 结果。
        """
        model = context.get("model") or os.getenv("LLM_MODEL") or "gpt-5.4"
        title = context.get("title") or "未命名任务"
        goal = context.get("goal") or "无特定目标"
        
        system_prompt, messages, anthropic_user_prompt = self._build_prompts(role, prompt, context, is_stream=False)
        user_prompt = prompt or f"请开始处理任务: {title}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        data = {
            "model": model,
            "messages": messages
        }
        
        url = f"{self.base_url}/chat/completions"
        req = urllib.request.Request(
            url, 
            data=json.dumps(data).encode("utf-8"), 
            headers=headers, 
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
                content = result["choices"][0]["message"]["content"]
                return LLMResult(content=content, structured={"role": role, "title": title, "goal": goal, "model": model})
        except urllib.error.HTTPError as e:
            try:
                error_body = e.read().decode("utf-8")
                error_json = json.loads(error_body)
                error_msg = error_json.get("error", {}).get("message") or error_body
            except Exception:
                error_msg = str(e)
                
            # 重试逻辑 1：遇到不支持该 API 格式的网关，降级为 Anthropic 协议进行重试
            if "不支持" in error_msg and "Api格式" in error_msg:
                anthropic_url = f"{self.base_url}/messages"
                anthropic_data = {
                    "model": model,
                    "max_tokens": 4096,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}]
                }
                anthropic_headers = dict(headers)
                anthropic_headers["anthropic-version"] = "2023-06-01"
                req = urllib.request.Request(anthropic_url, data=json.dumps(anthropic_data).encode("utf-8"), headers=anthropic_headers, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=120) as response:
                        result = json.loads(response.read().decode("utf-8"))
                        content = ""
                        for block in result.get("content", []):
                            if block.get("type") == "text":
                                content += block.get("text", "")
                        return LLMResult(content=content, structured={"role": role, "title": title, "goal": goal, "model": model})
                except Exception as retry_e:
                    error_msg = f"Anthropic 格式调用也失败: {str(retry_e)}"

            # 重试逻辑 2：当触发 Vip 拥堵、额度不足等情况时，自动 Fallback 到备用模型 DeepSeek-V3
            if "Vip" in error_msg or "不存在" in error_msg or "失败" in error_msg or "不支持" in error_msg:
                data["model"] = "DeepSeek-V3-0324"
                req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=120) as response:
                        result = json.loads(response.read().decode("utf-8"))
                        content = result["choices"][0]["message"]["content"]
                        return LLMResult(content=content, structured={"role": role, "title": title, "goal": goal, "model": "DeepSeek-V3-0324 (Fallback)"})
                except Exception:
                    pass

            return LLMResult(content=f"LLM 调用失败: {error_msg}", structured={"role": role, "error": error_msg, "model": model})
        except Exception as e:
            error_msg = f"LLM 调用失败: {str(e)}"
            return LLMResult(content=error_msg, structured={"role": role, "error": str(e), "model": model})

    def invoke_with_tools(
        self,
        role: str,
        prompt: str,
        context: Dict[str, Any],
        tools: List[Dict[str, Any]],
        tool_messages: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResult:
        """执行 OpenAI-compatible provider-native tool calling 请求。

        返回值的 structured.tool_calls 保留 provider 原生 tool call 结构，具体工具执行仍由
        AgentRuntime -> ToolService -> ToolPolicy 完成。
        """
        model = context.get("model") or os.getenv("LLM_MODEL") or "gpt-5.4"
        title = context.get("title") or "未命名任务"
        goal = context.get("goal") or "无特定目标"
        system_prompt, messages, _ = self._build_prompts(role, prompt, context, is_stream=False)

        for tool_message in tool_messages or []:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_message.get("tool_call_id"),
                    "name": tool_message.get("name"),
                    "content": tool_message.get("content", ""),
                }
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        data: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if tools:
            data["tools"] = tools
            data["tool_choice"] = "auto"

        url = f"{self.base_url}/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
                message = result["choices"][0]["message"]
                content = message.get("content") or ""
                return LLMResult(
                    content=content,
                    structured={
                        "role": role,
                        "title": title,
                        "goal": goal,
                        "model": model,
                        "provider_format": "chat.tools",
                        "tool_calls": message.get("tool_calls") or [],
                    },
                )
        except urllib.error.HTTPError as e:
            try:
                error_body = e.read().decode("utf-8")
                error_json = json.loads(error_body)
                error_msg = error_json.get("error", {}).get("message") or error_body
            except Exception:
                error_msg = str(e)

            # 不是所有兼容网关都支持 tools；此处明确降级到 JSON tool_calls 协议，而不是假装原生成功。
            if tools and ("tool" in error_msg.lower() or "不支持" in error_msg or "unsupported" in error_msg.lower()):
                compatibility_prompt = (
                    f"{prompt}\n\n"
                    "The current provider rejected native tool calling. If you need a tool, return raw JSON only:\n"
                    "{\"tool_calls\":[{\"tool_name\":\"knowledge.retrieve\",\"arguments\":{\"query\":\"...\"}}]}\n"
                    "If no tool is needed, return the final raw JSON output."
                )
                fallback = self.invoke(role, compatibility_prompt, context)
                fallback.structured["provider_format"] = "json.tool_calls.compat"
                fallback.structured["native_tool_calling_degraded"] = True
                fallback.structured["native_tool_calling_error"] = error_msg
                return fallback

            return LLMResult(
                content=f"LLM tool calling failed: {error_msg}",
                structured={"role": role, "error": error_msg, "model": model, "provider_format": "chat.tools"},
            )
        except Exception as e:
            return LLMResult(
                content=f"LLM tool calling failed: {str(e)}",
                structured={"role": role, "error": str(e), "model": model, "provider_format": "chat.tools"},
            )

    def invoke_stream(self, role: str, prompt: str, context: Dict[str, Any], telemetry: Optional[TelemetryCallback] = None):
        """执行流式 (Server-Sent Events) LLM 请求的生成器。

        通过 requests.post 流式拉取数据块，自动进行首字节时间 (TTFB) 遥测、对话块延时计算以及完成事件输出。
        在失败时支持自动切换至备用格式（Anthropic）或备用模型（DeepSeek-V3）的流式调用。

        Args:
            role: 执行任务的代理角色。
            prompt: 用户的当前提示词或具体指令。
            context: 任务关联的上下文。
            telemetry: 可选的遥测回调函数，用于日志追踪与分析。

        Yields:
            str | Dict[str, Any]: 产出的文本 Token 片段，或 fallback 提示事件。
        """
        model = context.get("model") or os.getenv("LLM_MODEL") or "gpt-5.4"
        title = context.get("title") or "未命名任务"
        goal = context.get("goal") or "无特定目标"
        
        system_prompt, messages, anthropic_user_prompt = self._build_prompts(role, prompt, context, is_stream=True)
        user_prompt = prompt or f"请开始处理任务: {title}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        data = {
            "model": model,
            "messages": messages,
            "stream": True
        }
        
        import requests
        import io
        import urllib.error
        url = f"{self.base_url}/chat/completions"
        call_id = f"llm_{uuid4().hex[:12]}"
        started_at = time.monotonic()
        self._emit(telemetry, "llm.call.started", {"call_id": call_id, "model": model, "base_url_host": self._host(), "provider_format": "chat", "stream": True})
        try:
            with requests.post(url, json=data, headers=headers, stream=True, timeout=10) as response:
                # 记录 TTFB (首字节收到时间)
                self._emit(telemetry, "llm.call.headers_received", {"call_id": call_id, "model": model, "base_url_host": self._host(), "provider_format": "chat", "status_code": response.status_code, "ttfb_ms": self._duration_ms(started_at)})
                if response.status_code != 200:
                    raise urllib.error.HTTPError(url, response.status_code, "HTTP Error", headers, io.BytesIO(response.content))
                
                first_token_seen = False
                chunk_count = 0
                output_chars = 0
                chunk_gaps = []
                last_chunk_at = None
                for line in response.iter_lines():
                    if line:
                        line = line.decode("utf-8").strip()
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    now = time.monotonic()
                                    if not first_token_seen:
                                        first_token_seen = True
                                        self._emit(telemetry, "llm.call.first_token", {"call_id": call_id, "model": model, "base_url_host": self._host(), "provider_format": "chat", "first_token_ms": self._duration_ms(started_at)})
                                    if last_chunk_at is not None:
                                        chunk_gaps.append(int((now - last_chunk_at) * 1000))
                                    last_chunk_at = now
                                    chunk_count += 1
                                    output_chars += len(content)
                                    yield content
                            except (json.JSONDecodeError, KeyError, IndexError):
                                pass
                self._emit(telemetry, "llm.call.completed", {"call_id": call_id, "model": model, "base_url_host": self._host(), "provider_format": "chat", "duration_ms": self._duration_ms(started_at), "output_chars": output_chars, "chunk_count": chunk_count, "max_chunk_gap_ms": max(chunk_gaps) if chunk_gaps else 0, "avg_chunk_gap_ms": int(sum(chunk_gaps) / len(chunk_gaps)) if chunk_gaps else 0})
                return
        except urllib.error.HTTPError as e:
            self._emit(telemetry, "llm.call.failed", {"call_id": call_id, "model": model, "base_url_host": self._host(), "provider_format": "chat", "duration_ms": self._duration_ms(started_at), "status_code": getattr(e, "code", None), "error_type": "HTTPError"})
            try:
                error_body = e.read().decode("utf-8")
                error_json = json.loads(error_body)
                error_msg = error_json.get("error", {}).get("message") or error_body
            except Exception:
                error_msg = str(e)
                
            # 流式重试逻辑 1：退回 Anthropic API 格式进行流式生成
            if "不支持" in error_msg and "Api格式" in error_msg:
                anthropic_url = f"{self.base_url}/messages"
                anthropic_call_id = f"llm_{uuid4().hex[:12]}"
                anthropic_started_at = time.monotonic()
                self._emit(telemetry, "llm.call.started", {"call_id": anthropic_call_id, "model": model, "base_url_host": self._host(), "provider_format": "anthropic", "stream": True})
                anthropic_data = {
                    "model": model,
                    "max_tokens": self._max_tokens_for_role(role),
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": anthropic_user_prompt}],
                    "stream": True
                }
                anthropic_headers = dict(headers)
                anthropic_headers["anthropic-version"] = "2023-06-01"
                try:
                    with requests.post(anthropic_url, json=anthropic_data, headers=anthropic_headers, stream=True, timeout=120) as response:
                        self._emit(telemetry, "llm.call.headers_received", {"call_id": anthropic_call_id, "model": model, "base_url_host": self._host(), "provider_format": "anthropic", "status_code": response.status_code, "ttfb_ms": self._duration_ms(anthropic_started_at)})
                        if response.status_code != 200:
                            raise Exception(response.text)
                        first_token_seen = False
                        chunk_count = 0
                        output_chars = 0
                        chunk_gaps = []
                        last_chunk_at = None
                        for line in response.iter_lines():
                            if line:
                                line = line.decode("utf-8").strip()
                                if line.startswith("data: "):
                                    data_str = line[6:]
                                    try:
                                        chunk = json.loads(data_str)
                                        if chunk.get("type") == "content_block_delta":
                                            delta = chunk.get("delta", {})
                                            content = delta.get("text", "") or delta.get("thinking", "")
                                            if content:
                                                now = time.monotonic()
                                                if not first_token_seen:
                                                    first_token_seen = True
                                                    self._emit(telemetry, "llm.call.first_token", {"call_id": anthropic_call_id, "model": model, "base_url_host": self._host(), "provider_format": "anthropic", "first_token_ms": self._duration_ms(anthropic_started_at)})
                                                if last_chunk_at is not None:
                                                    chunk_gaps.append(int((now - last_chunk_at) * 1000))
                                                last_chunk_at = now
                                                chunk_count += 1
                                                output_chars += len(content)
                                                yield content
                                    except json.JSONDecodeError:
                                        pass
                        self._emit(telemetry, "llm.call.completed", {"call_id": anthropic_call_id, "model": model, "base_url_host": self._host(), "provider_format": "anthropic", "duration_ms": self._duration_ms(anthropic_started_at), "output_chars": output_chars, "chunk_count": chunk_count, "max_chunk_gap_ms": max(chunk_gaps) if chunk_gaps else 0, "avg_chunk_gap_ms": int(sum(chunk_gaps) / len(chunk_gaps)) if chunk_gaps else 0})
                    return
                except Exception as retry_e:
                    self._emit(telemetry, "llm.call.failed", {"call_id": anthropic_call_id, "model": model, "base_url_host": self._host(), "provider_format": "anthropic", "duration_ms": self._duration_ms(anthropic_started_at), "error_type": type(retry_e).__name__})
                    error_msg = f"Anthropic 格式调用也失败: {str(retry_e)}"

            # 流式重试逻辑 2：触发拥堵、额度等限制，无缝 Fallback 降级到备用模型 DeepSeek-V3 流式生成
            if "Vip" in error_msg or "不存在" in error_msg or "失败" in error_msg or "不支持" in error_msg:
                yield {"type": "event", "name": "model.fallback", "message": "主模型响应超时，已无缝切换至备用模型 (DeepSeek-V3)"}
                data["model"] = "DeepSeek-V3-0324"
                fallback_call_id = f"llm_{uuid4().hex[:12]}"
                fallback_started_at = time.monotonic()
                self._emit(telemetry, "llm.call.fallback", {"from_model": model, "to_model": "DeepSeek-V3-0324", "base_url_host": self._host(), "reason_type": "provider_error"})
                self._emit(telemetry, "llm.call.started", {"call_id": fallback_call_id, "model": "DeepSeek-V3-0324", "base_url_host": self._host(), "provider_format": "chat_fallback", "stream": True})
                try:
                    with requests.post(url, json=data, headers=headers, stream=True, timeout=120) as response:
                        self._emit(telemetry, "llm.call.headers_received", {"call_id": fallback_call_id, "model": "DeepSeek-V3-0324", "base_url_host": self._host(), "provider_format": "chat_fallback", "status_code": response.status_code, "ttfb_ms": self._duration_ms(fallback_started_at)})
                        if response.status_code == 200:
                            first_token_seen = False
                            chunk_count = 0
                            output_chars = 0
                            chunk_gaps = []
                            last_chunk_at = None
                            for line in response.iter_lines():
                                if line:
                                    line = line.decode("utf-8").strip()
                                    if line.startswith("data: "):
                                        data_str = line[6:]
                                        if data_str == "[DONE]":
                                            break
                                        try:
                                            chunk = json.loads(data_str)
                                            delta = chunk["choices"][0].get("delta", {})
                                            content = delta.get("content", "")
                                            if content:
                                                now = time.monotonic()
                                                if not first_token_seen:
                                                    first_token_seen = True
                                                    self._emit(telemetry, "llm.call.first_token", {"call_id": fallback_call_id, "model": "DeepSeek-V3-0324", "base_url_host": self._host(), "provider_format": "chat_fallback", "first_token_ms": self._duration_ms(fallback_started_at)})
                                                if last_chunk_at is not None:
                                                    chunk_gaps.append(int((now - last_chunk_at) * 1000))
                                                last_chunk_at = now
                                                chunk_count += 1
                                                output_chars += len(content)
                                                yield content
                                        except (json.JSONDecodeError, KeyError, IndexError):
                                            pass
                            self._emit(telemetry, "llm.call.completed", {"call_id": fallback_call_id, "model": "DeepSeek-V3-0324", "base_url_host": self._host(), "provider_format": "chat_fallback", "duration_ms": self._duration_ms(fallback_started_at), "output_chars": output_chars, "chunk_count": chunk_count, "max_chunk_gap_ms": max(chunk_gaps) if chunk_gaps else 0, "avg_chunk_gap_ms": int(sum(chunk_gaps) / len(chunk_gaps)) if chunk_gaps else 0})
                            return
                        self._emit(telemetry, "llm.call.failed", {"call_id": fallback_call_id, "model": "DeepSeek-V3-0324", "base_url_host": self._host(), "provider_format": "chat_fallback", "duration_ms": self._duration_ms(fallback_started_at), "status_code": response.status_code, "error_type": "HTTPStatus"})
                except Exception:
                    self._emit(telemetry, "llm.call.failed", {"call_id": fallback_call_id, "model": "DeepSeek-V3-0324", "base_url_host": self._host(), "provider_format": "chat_fallback", "duration_ms": self._duration_ms(fallback_started_at), "error_type": "Exception"})

            yield f"\n\nLLM 调用失败: {error_msg}"
        except Exception as e:
            self._emit(telemetry, "llm.call.failed", {"call_id": call_id, "model": model, "base_url_host": self._host(), "provider_format": "chat", "duration_ms": self._duration_ms(started_at), "error_type": type(e).__name__})
            yield f"\n\nLLM 调用失败: {str(e)}"
