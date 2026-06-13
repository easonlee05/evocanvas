"""Real LLM implementation using OpenAI compatible API."""
import json
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
        """初始化 OpenAILLM 实例。

        Args:
            api_key: 用于接口鉴权的 API 密钥。
            base_url: LLM API 的基础访问 URL。
        """
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
        """触发遥测日志回调，发送结构化事件。

        Args:
            telemetry: 可选的遥测回调函数。
            event_type: 事件类型名称。
            payload: 事件关联 of 负载字典。
        """
        if telemetry:
            telemetry(event_type, payload)

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

    def _build_prompts(self, role: str, prompt: str, context: Dict[str, Any], is_stream: bool = False) -> Tuple[str, List[Dict[str, str]], str]:
        """构建大模型请求所需的 Prompts 结构。

        流程包括：
        1. 映射并拼接 System Prompt，附带本地锁定配置（Sticky Latch：MEMORY.md, CLAUDE.md）；
        2. 若为非 Writer 流式请求，附加字数控制指令；
        3. 对历史对话列表应用 Sliding Window（滑动窗口）压缩；
        4. 处理动态的用户 Prompt、追加上下文水合（Rehydration）；
        5. 生成 OpenAI 与 Anthropic 兼容的消息结构。

        Args:
            role: 执行任务的代理角色名称。
            prompt: 用户的当前提示词或具体指令。
            context: 任务关联的上下文，包含 title, goal, round_history 等。
            is_stream: 是否是流式调用，会影响系统指令的长度限制。

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
        
        role_map = {
            "compiler": "规范编译器 (Compiler)，负责将非结构化的业务意图进行标准化术语解析、AST抽象语法树生成，并生成 AI 技术同事可执行的任务包与验收协议。",
            "reviewer": "验收评审器 (Reviewer)，负责对比需求规格，对 AI 技术同事提交的代码与产物进行需求覆盖度、变更影响及安全审计，确保交付质量与规格契约一致。",
            "writer": "产物写入器 (Writer)，负责将编译或评审结论，按标准格式写入最终的交付资产（如 machine_spec、human_brief 或 review_result 等）。"
        }
        role_desc = role_map.get(role.lower(), f"专业协作角色: {role}")
        
        workspace_root = os.getcwd()
        
        # Sticky Latch: 始终把不可变规则放在 System Prompt 前方以强化模型对规范的记忆
        memory_path = os.path.join(workspace_root, "MEMORY.md")
        claude_path = os.path.join(workspace_root, "CLAUDE.md")
        
        fixed_context = ""
        for path, name in [(memory_path, "MEMORY.md"), (claude_path, "CLAUDE.md")]:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            fixed_context += f"\n【{name}】\n{content}\n"
                except Exception:
                    pass
        
        # 建立 System Prompt
        system_prompt = f"你现在扮演的角色是: {role}。\n角色定位: {role_desc}\n"
        if fixed_context:
            system_prompt += f"\n--- 全局系统锁定上下文 (Sticky Latch) ---\n{fixed_context}\n-----------------------------------\n"
        
        # 对于流式短回答（非 writer）施加严厉的系统限制，减少输出冗余
        if is_stream and role.lower() != "writer":
            system_prompt += "\n【系统指令】请保持极度精简、一针见血。输出字数必须严格控制在 100~300 字以内，严禁任何废话与长篇大论。"

        # Context Management: 基于滑动窗口压缩对话历史，避免 Token 溢出
        window_mgr = SlidingWindow(workspace_root=workspace_root, max_tokens=self._max_tokens_for_role(role))
        history_str, compactions = window_mgr.compact(context.get("round_history", []))
        if compactions > 0:
            self._emit(None, "llm.context.compacted", {"call_id": context.get("task_id", ""), "compactions": compactions})

        # 始终把变化的动态数据放在末尾 User Prompt
        dynamic_task_info = f"任务标题: {title}\n任务目标: {goal}\n\n"
        combined_user_content = dynamic_task_info
        
        if history_str:
            combined_user_content += f"以下是先前的协作讨论历史：\n\n{history_str}请根据上述历史背景继续你的发言。\n\n"
        
        combined_user_content += prompt or f"请开始处理任务: {title}"

        # Rehydration 引擎处理：动态水合上下文，在用户 Prompt 中还原引用内容
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
        model = context.get("model") or "gpt-5.4"
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
        model = context.get("model") or "gpt-5.4"
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
        model = context.get("model") or "gpt-5.4"
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
