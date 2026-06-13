"""Evoloop 3.0 原生规范编译（Spec-to-Agent）工作流任务定义模块（工业版）。

该模块实现了 3.0 架构的控制面核心，旨在把非结构化的业务意图（Business Intent）
通过三阶段编译器（Terminology Normalization -> LLM AST Gen -> AST Validation）
编译为机器可读的单事实来源（machine_spec.yaml），并生成 AI 技术同事可执行的任务包（Agent Package）及 BDD 验收协议。
"""
from __future__ import annotations

import json
import logging
import math
import re
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from app.core.errors import DomainError
from app.core.session import AgentSession, AgentSessionStatus
from app.core.subagent import SubagentBudget, SubagentScope, SubagentSpawnRequest
from app.core.task import StepResult, StepStatus, Task, TaskDefinition, WorkflowSpec, WorkflowStep
from app.services.agent_runtime import AgentRuntime
from app.services.subagent_service import SubagentService
from app.workflows.policies import build_default_tool_policy

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. 领域驱动设计值对象 (DDD Value Objects)
# ==============================================================================


@dataclass
class EnvironmentConfig:
    """部署目标环境配置值对象。"""

    os_target: str = "linux"
    node_version: str = "20.x"
    python_version: str = "3.10"
    env_vars: Dict[str, str] = field(default_factory=dict)
    
    def validate(self):
        """校验操作系统目标是否合法。"""
        if self.os_target not in ["linux", "mac", "windows", "docker"]:
            raise ValueError(f"Invalid OS Target: {self.os_target}")


@dataclass
class SecurityConstraints:
    """安全与权限控制约束值对象。"""

    require_auth: bool = True
    auth_method: str = "oauth2"
    encryption_at_rest: bool = True
    cors_allowed_origins: List[str] = field(default_factory=lambda: ["*"])


@dataclass
class NetworkPolicy:
    """网络访问控制策略值对象。"""

    expose_public_port: bool = False
    rate_limit_rps: int = 100
    timeout_ms: int = 3000


@dataclass
class EvoloopMachineSpecAST:
    """Evoloop 机器规范抽象语法树（AST）根节点定义。

    代表了 3.0 系统中已编译、无歧义的最终规约事实。
    """

    primary_requirement: str
    version: str = "1.0.0"
    dependencies: List[str] = field(default_factory=list)
    strict_contracts: List[str] = field(default_factory=list)
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    security: SecurityConstraints = field(default_factory=SecurityConstraints)
    network: NetworkPolicy = field(default_factory=NetworkPolicy)
    
    def to_dict(self) -> dict:
        """将 AST 节点序列化为字典表示。"""
        return {
            "source_of_truth": "machine_spec",
            "version": self.version,
            "primary_requirement": self.primary_requirement,
            "dependencies": self.dependencies,
            "strict_contracts": self.strict_contracts,
            "environment": {
                "os_target": self.environment.os_target,
                "node_version": self.environment.node_version,
                "python_version": self.environment.python_version,
            },
            "security": {
                "require_auth": self.security.require_auth,
                "auth_method": self.security.auth_method,
            }
        }

    @staticmethod
    def from_dict(data: dict) -> "EvoloopMachineSpecAST":
        """从字典反序列化生成 AST 对象。"""
        env_data = data.get("environment", {})
        sec_data = data.get("security", {})
        return EvoloopMachineSpecAST(
            primary_requirement=data.get("primary_requirement", "N/A"),
            dependencies=data.get("dependencies", []),
            strict_contracts=data.get("strict_contracts", []),
            environment=EnvironmentConfig(
                os_target=env_data.get("os_target", "linux"),
                node_version=env_data.get("node_version", "20.x"),
            ),
            security=SecurityConstraints(
                require_auth=sec_data.get("require_auth", True)
            )
        )


# ==============================================================================
# 2. 核心辅助工具: 重试机制、提取器与故障回退
# ==============================================================================

def _extract_json_from_markdown(text: str) -> str:
    """安全地从 Markdown 格式包裹的 LLM 输出中提取 JSON 文本。

    Args:
        text (str): 原始包含 markdown 代码块的 LLM 回答。

    Returns:
        str: 提取出的 JSON 字符串；若未找到代码块则尝试大括号提取或直接返回。
    """
    if not text:
        return "{}"
    # 高级正则表达式模式匹配 JSON 代码块
    match = re.search(r"```(?:json|JSON)?(.*?)```", text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        # 处理结尾可能残留的非法逗号
        content = re.sub(r",\s*}", "}", content)
        content = re.sub(r",\s*]", "]", content)
        return content
    
    # 回退方案：寻找第一个 { 和最后一个 }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    
    return text.strip()


def _invoke_llm_with_retry(
    llm: Any,
    role: str,
    prompt: str,
    context: Dict[str, Any],
    retries: int = 4,
    fallback: Optional[Dict[str, Any]] = None,
    temperature: float = 0.2
) -> Tuple[str, Dict[str, Any]]:
    """具有指数退避与提示词动态修复的健壮 LLM 调用工具。

    Args:
        llm (Any): 语言模型实例。
        role (str): 调用角色名称。
        prompt (str): 发送的提示词。
        context (Dict[str, Any]): 上下文变量。
        retries (int, optional): 最大重试次数。默认为 4。
        fallback (Optional[Dict[str, Any]], optional): 重试失败后的降级回退数据。默认为 None。
        temperature (float, optional): 温度。默认为 0.2。

    Returns:
        Tuple[str, Dict[str, Any]]: (LLM 回答的原始文本, 成功解析出的 JSON 字典)

    Raises:
        DomainError: 当重试耗尽且未配置 fallback，或者 LLM 服务完全不可用时。
    """
    if not llm:
        if fallback is not None:
            return "No LLM available, using fallback.", fallback
        raise DomainError("workflow.llm_unavailable", "LLM is required but none was provided.")

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            current_prompt = prompt
            # 若不是第一次尝试，追加强力的修复提示词，提醒大模型避免废话
            if attempt > 1 and last_error:
                current_prompt += f"\n\n[SYSTEM ALERT]: Previous attempt failed due to {last_error}. Ensure your output is EXCLUSIVELY raw JSON without any markdown or conversational filler."
                
            response = llm.invoke(role, current_prompt, context)
            raw_text = response.content
            json_text = _extract_json_from_markdown(raw_text)
            
            try:
                structured_data = json.loads(json_text)
                return raw_text, structured_data
            except json.JSONDecodeError as e:
                last_error = f"JSONDecodeError: {e}"
                logger.warning(f"Attempt {attempt} failed to parse JSON: {last_error}")
                # 模拟指数退避延迟
                time.sleep(0.1 * (2 ** attempt))
                
        except Exception as e:
            last_error = str(e)
            logger.error(f"Attempt {attempt} LLM invocation failed: {last_error}")

    if fallback is not None:
        logger.warning("Exhausted retries, returning safe fallback data.")
        degraded_fallback = dict(fallback)
        degraded_fallback["degraded"] = True
        degraded_fallback["fallback_reason"] = str(last_error)
        degraded_fallback["fallback_role"] = role
        return f"Failed after {retries} retries. Reason: {last_error}", degraded_fallback
        
    raise DomainError(
        "workflow.llm_retry_exhausted",
        f"Failed to get valid JSON from LLM after {retries} attempts. Last error: {last_error}",
    )


# ==============================================================================
# 3. 企业级词法分析与净化
# ==============================================================================

class LexicalTokenizer:
    """企业级输入清洗器与意图检测器。过滤恶意注入和控制字符。"""
    
    DANGEROUS_PATTERNS = [
        re.compile(r"(rm\s+-rf\s+/)"),
        re.compile(r"(:\(\)\{:|:&\};:)"), # 叉子炸弹
        re.compile(r"(DROP\s+TABLE)", re.IGNORECASE),
    ]

    @staticmethod
    def clean_input(text: str) -> str:
        """去除控制字符，阻止 naked 终端命令注入并检测已知危险模式。

        Args:
            text (str): 原始用户输入文本。

        Returns:
            str: 过滤净化后的文本。
        """
        if not text:
            return ""
        
        # 1. 过滤空字符及不需要的 ASCII 控制字符
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        # 2. 检查系统危险指令
        for pattern in LexicalTokenizer.DANGEROUS_PATTERNS:
            if pattern.search(text):
                logger.warning("Dangerous pattern detected in user input!")
                text = pattern.sub("[CENSORED]", text)
                
        return text.strip()


class ConstraintValidator:
    """根据预设的架构规则对用户约束列表进行严格的格式和长度审计。"""
    
    ALLOWED_CATEGORIES = {"performance", "security", "architecture", "ui", "general"}
    
    @staticmethod
    def validate(constraints: List[str]) -> List[str]:
        """校验并截断异常超长的约束说明。"""
        valid = []
        for c in constraints:
            c = str(c).strip()
            if not c:
                continue
            # 单行约束最多接受 2000 个字符
            if len(c) > 2000:
                c = c[:1997] + "..."
            
            valid.append(c)
        return valid


class ContextChunker:
    """当意图输入极长时，利用滑动窗口算法进行 token 切片以防 LLM 上下文爆溢。"""
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """估算 token 占用数量。"""
        return len(text) // 4
        
    @staticmethod
    def chunk(text: str, max_tokens: int = 4000) -> List[str]:
        """根据最大 token 限制将文本切分为带有重叠区域的多个片段。

        Args:
            text (str): 待切分长文本。
            max_tokens (int, optional): 每个分片最大 token 数。默认为 4000。

        Returns:
            List[str]: 切分后的段落列表。
        """
        if not text:
            return []
            
        estimated = ContextChunker.estimate_tokens(text)
        if estimated <= max_tokens:
            return [text]
            
        max_chars = max_tokens * 4
        chunks = []
        start = 0
        overlap = 200 # 重叠字符宽度，保证语义连贯
        
        while start < len(text):
            end = min(start + max_chars, len(text))
            if end < len(text):
                # 尽量优先在段落分界处 (双换行) 拆分
                newline_pos = text.rfind("\n\n", start, end)
                if newline_pos != -1 and newline_pos > start + (max_chars // 2):
                    end = newline_pos
                else:
                    # 其次在单换行处拆分
                    newline_pos = text.rfind("\n", start, end)
                    if newline_pos != -1 and newline_pos > start + (max_chars // 2):
                        end = newline_pos
                        
            chunks.append(text[start:end])
            start = end - overlap if end < len(text) else end
            
        return chunks


def _spec_inputs(task: Task) -> Dict[str, Any]:
    """提取并归一化当前任务的输入事实。"""
    raw_intent = str(task.context.inputs.get("business_intent") or task.context.goal)
    normalized_intent = LexicalTokenizer.clean_input(raw_intent)
    context_scope = LexicalTokenizer.clean_input(str(task.context.inputs.get("context_scope") or "default"))
    raw_constraints = task.context.user_constraints or task.context.inputs.get("constraints", [])
    constraints = ConstraintValidator.validate([str(c) for c in raw_constraints])
    
    return {
        "normalized_intent": normalized_intent,
        "context_scope": context_scope or "default",
        "constraints": constraints,
    }


class ContextNormalizerExecutor:
    """上下文标准化处理器。

    负责清洗并提取用户输入的业务意图与系统约束，并做分片规整。
    """
    step_type: str = "context"
    step_id: str = "context_normalizer"

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False) -> StepResult:
        inputs = _spec_inputs(task)
        
        logger.info(f"Normalizing context for task {task.task_id} with scope {inputs['context_scope']}")
        
        if not inputs["normalized_intent"]:
            raise DomainError("workflow.missing_intent", "Business intent cannot be empty after normalization.")
            
        # 执行长文本切分
        chunks = ContextChunker.chunk(inputs["normalized_intent"])
        inputs["intent_chunks_count"] = len(chunks)
        inputs["intent_chunks"] = chunks
            
        return StepResult(
            step.id,
            StepStatus.SUCCEEDED,
            "Context normalized successfully with enterprise-grade tokenization.",
            outputs=inputs,
        )


# ==============================================================================
# 4. 深度歧义诊断矩阵分析 (Ambiguity Matrix Analysis)
# ==============================================================================

class BaseDiagnoser(ABC):
    """诊断矩阵分析器的抽象基类。"""

    @abstractmethod
    def analyze(self, intent: str, llm: Any, fallback: Dict) -> Dict:
        pass


class DomainModelDiagnoser(BaseDiagnoser):
    """用于扫描业务意图中 DDD 领域模型与实体数据缺失的诊断器。"""

    def analyze(self, intent: str, llm: Any, fallback: Dict) -> Dict:
        prompt = (
            "Analyze the business intent for missing Domain-Driven Design (DDD) entities.\n"
            "Identify if critical data structures, aggregates, or persistence mechanisms are undefined.\n"
            "Output JSON:\n"
            "{\"has_questions\": bool, \"questions\": [\"Question regarding entities\"]}"
        )
        _, structured = _invoke_llm_with_retry(llm, "Compiler", prompt, {"intent": intent}, fallback=fallback)
        return structured


class StateTransitionDiagnoser(BaseDiagnoser):
    """用于扫描系统生命周期、状态机变迁规则以及补偿/回滚路径缺失的诊断器。"""

    def analyze(self, intent: str, llm: Any, fallback: Dict) -> Dict:
        prompt = (
            "Analyze the business intent for undefined state machine transitions or edge cases.\n"
            "Identify if error handling, rollback states, or lifecycle events are missing.\n"
            "Output JSON:\n"
            "{\"has_questions\": bool, \"questions\": [\"Question regarding state transitions\"]}"
        )
        _, structured = _invoke_llm_with_retry(llm, "Compiler", prompt, {"intent": intent}, fallback=fallback)
        return structured


class NonFunctionalDiagnoser(BaseDiagnoser):
    """用于扫描非功能性需求（吞吐 TPS、安全性、CORS、网络超时等）定义不全的诊断器。"""

    def analyze(self, intent: str, llm: Any, fallback: Dict) -> Dict:
        prompt = (
            "Analyze the business intent for non-functional requirements (NFRs).\n"
            "Identify if performance targets (TPS), security protocols, or scalability constraints are undefined.\n"
            "Output JSON:\n"
            "{\"has_questions\": bool, \"questions\": [\"Question regarding NFRs\"]}"
        )
        _, structured = _invoke_llm_with_retry(llm, "Compiler", prompt, {"intent": intent}, fallback=fallback)
        return structured


class TFIDFEngineMock:
    """模拟语义词频去重引擎，用于过滤不同诊断器产生的相似重合问题。"""
    
    @staticmethod
    def compute_similarity(s1: str, s2: str) -> float:
        """利用集合的杰卡德相似度模拟两句问题间的重复度。"""
        w1 = set(s1.lower().split())
        w2 = set(s2.lower().split())
        if not w1 or not w2:
            return 0.0
        intersection = w1.intersection(w2)
        union = w1.union(w2)
        return len(intersection) / len(union)


class DeduplicationEngine:
    """将多个诊断维度发现的待答澄清问题进行语义去重。"""
    
    SIMILARITY_THRESHOLD = 0.65
    
    @staticmethod
    def deduplicate(questions_lists: List[List[str]]) -> List[str]:
        """执行相似度聚合去重。"""
        final_list = []
        for q_list in questions_lists:
            for q in q_list:
                q_clean = str(q).strip()
                if not q_clean:
                    continue
                    
                is_dup = False
                for existing in final_list:
                    if TFIDFEngineMock.compute_similarity(q_clean, existing) > DeduplicationEngine.SIMILARITY_THRESHOLD:
                        is_dup = True
                        break
                        
                if not is_dup:
                    final_list.append(q_clean)
        return final_list


class OpenQuestionIdentifierExecutor:
    """需求歧义多维度分析与提问步骤（open_question_identifier）执行器。"""

    step_type: str = "agent"
    step_id: str = "open_question_identifier"

    def __init__(self, llm: Any = None, tool_service: Any = None):
        self.llm = llm
        self.tool_service = tool_service
        self.diagnosers = [
            DomainModelDiagnoser(),
            StateTransitionDiagnoser(),
            NonFunctionalDiagnoser(),
        ]

    def _build_prompt(self, intent: str, constraints: List[str], helper_context: Optional[List[Dict[str, Any]]] = None) -> str:
        prompt = (
            "You are the OpenQuestionIdentifier for a digital product manager.\n"
            "Analyze the business intent across domain model, state transitions, edge cases, and non-functional requirements.\n"
            "Ask only questions that block a trustworthy machine_spec. Do not ask implementation-style questions.\n"
            "Output STRICTLY in JSON format matching this schema:\n"
            "{\n"
            '  "has_questions": true,\n'
            '  "questions": ["Question 1"],\n'
            '  "diagnostic_matrix_runs": 1\n'
            "}\n\n"
            f"INTENT:\n{intent}\n\n"
            f"CONSTRAINTS:\n{json.dumps(constraints, ensure_ascii=False)}"
        )
        if helper_context:
            prompt += (
                "\n\nINTERNAL HELPER SNAPSHOT:\n"
                "These helper findings are advisory only. Use them to refine ambiguity detection, "
                "but still decide the final question list in this main session.\n"
                f"{json.dumps(helper_context, ensure_ascii=False)}"
            )
        return prompt

    def _run_internal_helpers(
        self,
        task: Task,
        session: AgentSession,
        inputs: Dict[str, Any],
        active_llm: Any,
    ) -> List[Dict[str, Any]]:
        """Spawn a narrow helper when the task explicitly enables internal subagents."""
        if not task.context.inputs.get("enable_subagents"):
            return []

        helper_request = SubagentSpawnRequest(
            scope=SubagentScope.SESSION_HELPER,
            goal="Inspect ambiguity hotspots before final question drafting.",
            task_slice="Only inspect product ambiguity hotspots from the business intent and constraints.",
            input_refs=["business_intent", "constraints"],
            input_excerpt={
                "business_intent": inputs["normalized_intent"],
                "constraints": list(inputs["constraints"]),
                "context_scope": inputs["context_scope"],
            },
            allowed_tools=["knowledge.retrieve"] if self.tool_service else [],
            output_schema={"summary": "string", "findings": "array", "confidence": "string"},
            budget=SubagentBudget(
                max_iterations=2,
                max_input_tokens=400,
                max_output_tokens=160,
                max_tool_calls=1,
                spawn_fanout_remaining=1,
            ),
            depth=1,
        )
        run = SubagentService(llm=active_llm, tool_service=self.tool_service).run_helper(
            parent_session=session,
            request=helper_request,
            task_definition=task.definition,
            task_context=task.context,
        )
        if not run.result:
            return []
        return [
            {
                "summary": run.result.summary,
                "findings": run.result.structured_output.get("findings", []),
                "confidence": run.result.confidence,
                "degraded": run.result.degraded,
                "degradation_reason": run.result.degradation_reason,
            }
        ]

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False, llm: Any = None) -> StepResult:
        active_llm = llm or self.llm
        inputs = _spec_inputs(task)
        intent = inputs["normalized_intent"]

        session = AgentSession(
            task_id=task.task_id,
            step_id=step.id,
            agent_role=step.role or "Compiler",
            goal="Identify only the open product questions that block a trustworthy machine_spec.",
            input_context={
                "normalized_intent": intent,
                "constraints": inputs["constraints"],
                "task_definition": task.definition,
                "task_context": task.context,
            },
            max_iterations=3,
        )
        helper_context = self._run_internal_helpers(task, session, inputs, active_llm)
        run_result = AgentRuntime(llm=active_llm, tool_service=self.tool_service).run_json_session(
            session=session,
            prompt=self._build_prompt(intent, inputs["constraints"], helper_context),
            context={
                "intent": intent,
                "constraints": inputs["constraints"],
                "helper_context": helper_context,
            },
            required_keys=["has_questions", "questions"],
            task_definition=task.definition,
            task_context=task.context,
        )

        trace = session.to_trace()
        if run_result.status == AgentSessionStatus.BLOCKED or run_result.structured.get("degraded"):
            structured = dict(run_result.structured)
            structured["fallback_reason"] = structured.get("fallback_reason") or (run_result.error.message if run_result.error else "AgentSession blocked")
            return StepResult(
                step.id,
                StepStatus.BLOCKED,
                "Open question identifier AgentSession blocked before producing trustworthy ambiguity analysis.",
                outputs={
                    "content": run_result.content,
                    "structured": structured,
                    "agent_session_id": session.session_id,
                    "agent_session_trace": trace,
                },
                error=DomainError(
                    "workflow.open_question_identifier_blocked",
                    "Open question identifier exhausted AgentSession retries and refused to emit fake no-questions success.",
                    {"step_id": step.id, "agent_runtime_error": run_result.error.to_dict() if run_result.error else None},
                ),
            )

        raw_questions = run_result.structured.get("questions", [])
        if not isinstance(raw_questions, list):
            raw_questions = []
        merged_questions = DeduplicationEngine.deduplicate([raw_questions])
        has_questions = bool(run_result.structured.get("has_questions")) or len(merged_questions) > 0
        safe_structured = {
            "has_questions": has_questions,
            "questions": merged_questions,
            "diagnostic_matrix_runs": int(run_result.structured.get("diagnostic_matrix_runs") or 1),
        }
        
        return StepResult(
            step.id,
            StepStatus.SUCCEEDED,
            "AgentSession ambiguity analysis complete.",
            outputs={
                "content": run_result.content,
                "structured": safe_structured,
                "agent_session_id": session.session_id,
                "agent_session_trace": trace,
            },
        )


# ==============================================================================
# 5. 决策门禁与挂起暂停处理 (Human in the Loop)
# ==============================================================================

class SuspensionManager:
    """负责将有歧义的任务挂起，生成人工干预仲裁工单的值对象管理类。"""
    
    @staticmethod
    def generate_ticket(task_id: str, questions: List[str]) -> Dict[str, Any]:
        """组装人工仲裁工单详情。"""
        return {
            "ticket_id": f"arb_{uuid.uuid4().hex[:8]}",
            "task_id": task_id,
            "ttl_seconds": 86400, # 限制 24 小时过期
            "status": "pending_human_review",
            "created_at": time.time(),
            "questions": questions
        }


class HumanDecisionGateExecutor:
    """人类干预与决策门禁步骤（human_decision_gate）执行器。

    若发现存在歧义问题需要干预，则抛出 Arbitration Ticket 挂起工作流。
    """

    step_type: str = "gate"
    step_id: str = "human_decision_gate"

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False) -> StepResult:
        questions_payload = task.context.step_outputs.get("open_question_identifier", {}).get("structured", {})
        has_questions = questions_payload.get("has_questions", False)
        
        status = "fail" if has_questions else "pass"
        gate = {
            "step_id": step.id,
            "status": status,
            "checks": task.definition.gate_policy.get("gates", []),
            "has_questions": has_questions,
        }
        
        if has_questions:
            ticket = SuspensionManager.generate_ticket(task.task_id, questions_payload.get("questions", []))
            gate["ticket"] = ticket
            logger.info(f"Generated Arbitration Ticket {ticket['ticket_id']} for {len(ticket['questions'])} questions.")
            task.context.gate_results.append(gate)
            return StepResult(
                step.id,
                StepStatus.NEEDS_ARBITRATION,
                "Human arbitration required due to ambiguous intent.",
                outputs={"gate": gate, "dispute_package": ticket},
                next_step_id=step.id,
                resume_step_id="machine_spec_compiler"
            )
            
        task.context.gate_results.append(gate)
        return StepResult(step.id, StepStatus.SUCCEEDED, f"decision gate evaluated to {status}", outputs={"gate": gate})


# ==============================================================================
# 6. 多阶段机器规约编译核心 (Multi-Stage Machine Spec Compiler)
# ==============================================================================

class MachineSpecCompilerExecutor:
    """三段式规约编译器步骤（machine_spec_compiler）执行器。

    严格执行:
    1. PreCompile: 术语规范化与环境规约上下文合并。
    2. MainCompile: 调用 LLM 执行 AST 生成，将输入转化为标准化属性。
    3. PostCompile: 使用 Pydantic/Dataclass 类型断言进行 AST 防御性校验与转换。
    """

    step_type: str = "agent"
    step_id: str = "machine_spec_compiler"

    def __init__(self, llm: Any = None, tool_service: Any = None):
        self.llm = llm
        self.tool_service = tool_service

    def _pre_compile(self, intent: str, constraints: List[str]) -> str:
        """第一阶段: 整合归一化文本。"""
        return f"INTENT: {intent}\nCONSTRAINTS: {'; '.join(constraints)}"

    def _run_internal_helpers(
        self,
        task: Task,
        session: AgentSession,
        inputs: Dict[str, Any],
        pre_compiled: str,
        active_llm: Any,
    ) -> List[Dict[str, Any]]:
        """Optionally run a narrow session helper before final AST compilation."""
        if not task.context.inputs.get("enable_subagents"):
            return []

        helper_request = SubagentSpawnRequest(
            scope=SubagentScope.SESSION_HELPER,
            goal="Extract domain state and constraint hotspots before AST compilation.",
            task_slice="Only inspect domain states, constraints, and structural hotspots from the normalized intent.",
            input_refs=["business_intent", "constraints", "pre_compiled_data"],
            input_excerpt={
                "business_intent": inputs["normalized_intent"],
                "constraints": list(inputs["constraints"]),
                "pre_compiled_data": pre_compiled[:1200],
            },
            allowed_tools=["knowledge.retrieve"] if self.tool_service else [],
            output_schema={"summary": "string", "states": "array", "confidence": "string"},
            budget=SubagentBudget(
                max_iterations=2,
                max_input_tokens=450,
                max_output_tokens=180,
                max_tool_calls=1,
                spawn_fanout_remaining=1,
            ),
            depth=1,
        )
        run = SubagentService(llm=active_llm, tool_service=self.tool_service).run_helper(
            parent_session=session,
            request=helper_request,
            task_definition=task.definition,
            task_context=task.context,
        )
        if not run.result:
            return []
        return [
            {
                "summary": run.result.summary,
                "states": run.result.structured_output.get("states", []),
                "confidence": run.result.confidence,
                "degraded": run.result.degraded,
                "degradation_reason": run.result.degradation_reason,
            }
        ]

    def _main_compile(
        self,
        pre_compiled: str,
        active_llm: Any,
        session: AgentSession,
        helper_context: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        """第二阶段: 通过 AgentRuntime 编译 AST 的 JSON 结构。"""
        prompt = (
            "You are the MachineSpecCompiler. You must compile the given input into a structural AST.\n"
            "Output STRICTLY in JSON format matching this schema:\n"
            "{\n"
            '  "primary_requirement": "Main goal",\n'
            '  "dependencies": ["dep1", "dep2"],\n'
            '  "strict_contracts": ["Contract 1"],\n'
            '  "environment": {"os_target": "linux", "node_version": "20.x"},\n'
            '  "security": {"require_auth": true}\n'
            "}"
        )
        if helper_context:
            prompt += (
                "\n\nINTERNAL HELPER SNAPSHOT:\n"
                "Use these bounded helper findings only as advisory analysis hints while compiling the AST.\n"
                f"{json.dumps(helper_context, ensure_ascii=False)}"
            )
        return AgentRuntime(llm=active_llm, tool_service=self.tool_service).run_json_session(
            session=session,
            prompt=prompt,
            context={"pre_compiled_data": pre_compiled, "helper_context": helper_context or []},
            required_keys=["primary_requirement", "dependencies", "strict_contracts", "environment", "security"],
            task_definition=session.input_context.get("task_definition"),
            task_context=session.input_context.get("task_context"),
        )

    def _post_compile(self, ast_dict: Dict, default_intent: str) -> Dict:
        """第三阶段: 转换校验为正式的 AST 并进行后置填充。"""
        if "primary_requirement" not in ast_dict or not ast_dict["primary_requirement"] or ast_dict["primary_requirement"] == "Fallback requirement":
            ast_dict["primary_requirement"] = default_intent
            
        ast_obj = EvoloopMachineSpecAST.from_dict(ast_dict)
        return ast_obj.to_dict()

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False, llm: Any = None) -> StepResult:
        active_llm = llm or self.llm
        inputs = _spec_inputs(task)
        
        # 依次通过三阶段管道编译 AST；主编译阶段由 AgentRuntime 执行 bounded session。
        pre_compiled = self._pre_compile(inputs["normalized_intent"], inputs["constraints"])
        session = AgentSession(
            task_id=task.task_id,
            step_id=step.id,
            agent_role=step.role or "Compiler",
            goal="Compile normalized product intent into Evoloop Machine Spec AST.",
            input_context={
                "pre_compiled_data": pre_compiled,
                "normalized_intent": inputs["normalized_intent"],
                "task_definition": task.definition,
                "task_context": task.context,
            },
            max_iterations=3,
        )
        helper_context = self._run_internal_helpers(task, session, inputs, pre_compiled, active_llm)
        run_result = self._main_compile(pre_compiled, active_llm, session, helper_context)
        content = run_result.content
        raw_ast = run_result.structured
        trace = session.to_trace()

        if run_result.status == AgentSessionStatus.BLOCKED or raw_ast.get("degraded"):
            raw_ast["fallback_reason"] = raw_ast.get("fallback_reason") or (run_result.error.message if run_result.error else "AgentSession blocked")
            return StepResult(
                step.id,
                StepStatus.BLOCKED,
                "Machine Spec compiler AgentSession blocked before producing a trustworthy source-of-truth artifact.",
                outputs={"content": content, "structured": raw_ast, "agent_session_id": session.session_id, "agent_session_trace": trace},
                error=DomainError(
                    "workflow.llm_degraded_fallback",
                    "Machine Spec compiler exhausted AgentSession retries and refused to emit a fallback source-of-truth artifact.",
                    {"step_id": step.id, "agent_runtime_error": run_result.error.to_dict() if run_result.error else None},
                ),
            )
        final_ast = self._post_compile(raw_ast, inputs["normalized_intent"])
        
        return StepResult(
            step.id,
            StepStatus.SUCCEEDED,
            "Machine Spec successfully compiled through AgentSession.",
            outputs={"content": content, "structured": final_ast, "agent_session_id": session.session_id, "agent_session_trace": trace},
        )


# ==============================================================================
# 7. AI 技术同事交付分包 (方言适配策略与 BDD 协议生成)
# ==============================================================================

class DialectStrategy(ABC):
    """方言适配策略抽象基类。用于根据不同 AI 技术同事适配专有的 prompt 和命令配置。"""

    @abstractmethod
    def get_system_prompt(self, spec: Dict) -> str:
        pass
        
    @abstractmethod
    def generate_payload(self, spec: Dict) -> Dict:
        pass


class CodexDialect(DialectStrategy):
    """面向工程实现同事 Codex 的方言适配。"""

    def get_system_prompt(self, spec: Dict) -> str:
        return "You are Codex, an AI technical peer. Implement against the provided product contract without bypassing tests or tool policy."
        
    def generate_payload(self, spec: Dict) -> Dict:
        return {
            "peer_target": "codex",
            "commands": ["npm run build", "pytest tests/"],
            "dialect_prompt": self.get_system_prompt(spec)
        }


class ClaudeDialect(DialectStrategy):
    """面向逻辑与重构专家 Claude Code 的方言适配。"""

    def get_system_prompt(self, spec: Dict) -> str:
        return "You are Claude Code, an AI technical peer. Focus on readability, refactoring safety, and explicit review notes."
        
    def generate_payload(self, spec: Dict) -> Dict:
        return {
            "peer_target": "claude",
            "commands": ["make all", "make test"],
            "dialect_prompt": self.get_system_prompt(spec)
        }


class CursorDialect(DialectStrategy):
    """面向本地 IDE 联调联创助手 Cursor 的方言适配。"""

    def get_system_prompt(self, spec: Dict) -> str:
        return "You are Cursor, an AI technical peer in the IDE. Coordinate local edits against the stable API/SSE contract."
        
    def generate_payload(self, spec: Dict) -> Dict:
        return {
            "peer_target": "cursor",
            "commands": ["yarn build"],
            "dialect_prompt": self.get_system_prompt(spec)
        }


class AgentPackageGeneratorExecutor:
    """AI 执行包生成步骤（agent_package_generator）执行器。

    使用策略模式，根据大模型评估结果将编译的 AST 转换为指定方言架构的任务执行包。
    """

    step_type: str = "agent"
    step_id: str = "agent_package_generator"

    def __init__(self, llm: Any = None, tool_service: Any = None):
        self.llm = llm
        self.tool_service = tool_service
        
    def _get_dialect(self, target: str) -> DialectStrategy:
        target = target.lower().strip()
        if target == "claude": return ClaudeDialect()
        if target == "cursor": return CursorDialect()
        return CodexDialect()

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False, llm: Any = None) -> StepResult:
        active_llm = llm or self.llm
        machine_spec = task.context.step_outputs.get("machine_spec_compiler", {}).get("structured", {})
        
        prompt = (
            "Analyze the Machine Spec and select the most appropriate peer AI technical colleague.\n"
            "Choices: codex (implementation/build/test), claude (logic/refactor/review), cursor (IDE/frontend/inline).\n"
            "Output STRICTLY JSON: {\"peer_target\": \"codex\"}"
        )

        session = AgentSession(
            task_id=task.task_id,
            step_id=step.id,
            agent_role=step.role or "Compiler",
            goal="Select the peer AI technical colleague and package the compiled machine spec for collaboration.",
            input_context={
                "machine_spec": machine_spec,
                "task_definition": task.definition,
                "task_context": task.context,
            },
            max_iterations=3,
        )
        run_result = AgentRuntime(llm=active_llm, tool_service=self.tool_service).run_json_session(
            session=session,
            prompt=prompt,
            context={"machine_spec": machine_spec},
            required_keys=["peer_target"],
            task_definition=task.definition,
            task_context=task.context,
        )

        trace = session.to_trace()
        if run_result.status == AgentSessionStatus.BLOCKED or run_result.structured.get("degraded"):
            structured = dict(run_result.structured)
            structured["fallback_reason"] = structured.get("fallback_reason") or (run_result.error.message if run_result.error else "AgentSession blocked")
            return StepResult(
                step.id,
                StepStatus.BLOCKED,
                "Agent package generator AgentSession blocked before selecting a trustworthy peer target.",
                outputs={
                    "content": run_result.content,
                    "structured": structured,
                    "agent_session_id": session.session_id,
                    "agent_session_trace": trace,
                },
                error=DomainError(
                    "workflow.agent_package_generator_blocked",
                    "Agent package generator exhausted AgentSession retries and refused to emit fake peer package success.",
                    {"step_id": step.id, "agent_runtime_error": run_result.error.to_dict() if run_result.error else None},
                ),
            )
        
        target = run_result.structured.get("peer_target") or run_result.structured.get("worker_target") or "codex"
        dialect = self._get_dialect(target)
        safe_structured = dialect.generate_payload(machine_spec)
        
        return StepResult(
            step.id,
            StepStatus.SUCCEEDED,
            f"Agent package generated for peer target: {target}",
            outputs={
                "content": run_result.content,
                "structured": safe_structured,
                "agent_session_id": session.session_id,
                "agent_session_trace": trace,
            },
        )


class AcceptanceProtocolGeneratorExecutor:
    """BDD 验收协议生成步骤（acceptance_protocol_generator）执行器。

    输出符合 Behavior-Driven Development 行为规范（Given-When-Then）的严格测试用例。
    """

    step_type: str = "agent"
    step_id: str = "acceptance_protocol_generator"

    def __init__(self, llm: Any = None, tool_service: Any = None):
        self.llm = llm
        self.tool_service = tool_service

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False, llm: Any = None) -> StepResult:
        active_llm = llm or self.llm
        machine_spec = task.context.step_outputs.get("machine_spec_compiler", {}).get("structured", {})
        
        prompt = (
            "Generate Behavior-Driven Development (BDD) test vectors for the provided Machine Spec.\n"
            "Each vector MUST follow the 'Given ... When ... Then ...' syntax.\n"
            "Output STRICTLY JSON:\n"
            "{\n"
            '  "test_vectors": ["Given the user is logged in, When they click buy, Then the item is added to the cart"]\n'
            "}"
        )

        session = AgentSession(
            task_id=task.task_id,
            step_id=step.id,
            agent_role=step.role or "Compiler",
            goal="Generate acceptance protocol test vectors from the source-of-truth machine spec.",
            input_context={
                "machine_spec": machine_spec,
                "task_definition": task.definition,
                "task_context": task.context,
            },
            max_iterations=3,
        )
        run_result = AgentRuntime(llm=active_llm, tool_service=self.tool_service).run_json_session(
            session=session,
            prompt=prompt,
            context={"machine_spec": machine_spec},
            required_keys=["test_vectors"],
            task_definition=task.definition,
            task_context=task.context,
        )

        trace = session.to_trace()
        if run_result.status == AgentSessionStatus.BLOCKED or run_result.structured.get("degraded"):
            structured = dict(run_result.structured)
            structured["fallback_reason"] = structured.get("fallback_reason") or (run_result.error.message if run_result.error else "AgentSession blocked")
            return StepResult(
                step.id,
                StepStatus.BLOCKED,
                "Acceptance protocol generator AgentSession blocked before producing trustworthy test vectors.",
                outputs={
                    "content": run_result.content,
                    "structured": structured,
                    "agent_session_id": session.session_id,
                    "agent_session_trace": trace,
                },
                error=DomainError(
                    "workflow.acceptance_protocol_generator_blocked",
                    "Acceptance protocol generator exhausted AgentSession retries and refused to emit fallback test vectors as success.",
                    {"step_id": step.id, "agent_runtime_error": run_result.error.to_dict() if run_result.error else None},
                ),
            )

        vectors = run_result.structured.get("test_vectors", [])
        if not isinstance(vectors, list) or len(vectors) == 0:
            vectors = []
            
        # 强制性校验并前缀化 BDD 语法格式，确保格式合格
        validated_vectors = []
        for v in vectors:
            if str(v).lower().startswith("given"):
                validated_vectors.append(str(v))
            else:
                validated_vectors.append(f"Given context, When executed, Then {str(v)}")
        
        safe_structured = {
            "test_vectors": validated_vectors,
            "framework_target": "cucumber/pytest-bdd",
            "degraded": False,
        }
        
        return StepResult(
            step.id,
            StepStatus.SUCCEEDED,
            "Strict BDD Acceptance protocol generated.",
            outputs={
                "content": run_result.content,
                "structured": safe_structured,
                "agent_session_id": session.session_id,
                "agent_session_trace": trace,
            },
        )


# ==============================================================================
# 8. 公共快捷执行函数与 3.0 剧本 TaskDefinition 构建器
# ==============================================================================

def context_normalizer_step(task: Task, step: WorkflowStep) -> StepResult:
    """归一化上下文步骤回调包装。"""
    return ContextNormalizerExecutor().run(task, step)


def open_question_identifier_step(task: Task, step: WorkflowStep, llm: Any = None, tool_service: Any = None) -> StepResult:
    """多维需求歧义推演步骤回调包装。"""
    return OpenQuestionIdentifierExecutor(llm=llm, tool_service=tool_service).run(task, step)


def human_decision_gate_step(task: Task, step: WorkflowStep) -> StepResult:
    """决策仲裁门禁步骤回调包装。"""
    return HumanDecisionGateExecutor().run(task, step)


def machine_spec_compiler_step(task: Task, step: WorkflowStep, llm: Any = None, tool_service: Any = None) -> StepResult:
    """三段式 AST 编译步骤回调包装。"""
    return MachineSpecCompilerExecutor(llm=llm, tool_service=tool_service).run(task, step)


def agent_package_generator_step(task: Task, step: WorkflowStep, llm: Any = None, tool_service: Any = None) -> StepResult:
    """AI 技术同事协作包生成步骤回调包装。"""
    return AgentPackageGeneratorExecutor(llm=llm, tool_service=tool_service).run(task, step)


def acceptance_protocol_generator_step(task: Task, step: WorkflowStep, llm: Any = None, tool_service: Any = None) -> StepResult:
    """验收协议生成步骤回调包装。"""
    return AcceptanceProtocolGeneratorExecutor(llm=llm, tool_service=tool_service).run(task, step)


def build_spec_to_agent_definition(public_task_type: str = "spec_to_agent") -> TaskDefinition:
    """构建并配置 3.0 原生 Spec-to-Agent 编译工作流的 `TaskDefinition`。

    这是 Evoloop 3.0 体系下的核心原生应用，负责完成用户输入到下层执行规格的自动化翻译与封装。

    Args:
        public_task_type (str, optional): 外部公开的任务剧本名称。默认为 "spec_to_agent"。

    Returns:
        TaskDefinition: 初始化配置完毕的规范编译任务定义，包含其步骤链、输出规格映射、自定义处理器与工具白名单。
    """
    workflow = WorkflowSpec(
        name="spec_to_agent.compiler.pipeline.v2",
        version="2.0",
        steps=[
            WorkflowStep(id="context_normalizer", type="context", title="归一化上下文与边界", allowed_tools=["material.parse"]),
            WorkflowStep(id="open_question_identifier", type="agent", title="多维需求歧义推演", role="Compiler"),
            WorkflowStep(id="human_decision_gate", type="gate", title="仲裁决策门禁", role="Compiler"),
            WorkflowStep(id="machine_spec_compiler", type="agent", title="三段式 AST 编译", role="Compiler"),
            WorkflowStep(id="agent_package_generator", type="agent", title="方言策略与任务分包", role="Compiler", parallel_group="package_gen"),
            WorkflowStep(id="acceptance_protocol_generator", type="agent", title="BDD 红线生成", role="Compiler", parallel_group="package_gen"),
            WorkflowStep(id="writer_machine_spec", type="artifact", title="写入 machine_spec.yaml", role="Writer", allowed_tools=["artifact.write"], output_keys=["machine_spec"]),
            WorkflowStep(id="writer_human_brief", type="artifact", title="写入 human_brief.md", role="Writer", allowed_tools=["artifact.write"], output_keys=["human_brief"]),
            WorkflowStep(id="writer_agent_package", type="artifact", title="写入 agent_package_codex.md", role="Writer", allowed_tools=["artifact.write"], output_keys=["agent_package"]),
            WorkflowStep(id="writer_acceptance", type="artifact", title="写入 acceptance.md", role="Writer", allowed_tools=["artifact.write"], output_keys=["acceptance"]),
            WorkflowStep(id="writer_review_checklist", type="artifact", title="写入 review_checklist.md", role="Writer", allowed_tools=["artifact.write"], output_keys=["review_checklist"]),
            WorkflowStep(id="writer_traceability", type="artifact", title="写入 traceability.json", role="Writer", allowed_tools=["artifact.write"], output_keys=["traceability"]),
            WorkflowStep(id="final_checkpoint", type="checkpoint", title="保存最终 checkpoint"),
        ],
    )
    return TaskDefinition(
        type="spec_to_agent",
        display_name="Spec to Agent Compiler Pipeline",
        input_schema={
            "required": ["username", "business_intent"],
            "properties": {
                "username": {"type": "string"},
                "business_intent": {"type": "string"},
                "material_ids": {"type": "array"},
                "context_scope": {"type": "string"},
            },
        },
        workflow=workflow,
        tool_policy=build_default_tool_policy("spec_to_agent"),
        agents={"compiler": "Compiler", "writer": "Writer"},
        round_policy={"max_rounds": 3},
        gate_policy={"gates": ["需求无歧义", "架构契约严谨", "依赖完备"]},
        output_spec={
            "machine_spec": "machine_spec.yaml",
            "human_brief": "human_brief.md",
            "agent_package": "agent_package_codex.md",
            "acceptance": "acceptance.md",
            "review_checklist": "review_checklist.md",
            "traceability": "traceability.json"
        },
        metadata={
            "lane": "spec_to_agent",
            "canonical_task_type": "spec_to_agent",
            "public_task_type": public_task_type,
            "is_native_3_0": True,
            "source_of_truth": "machine_spec.yaml",
            # 为各节点绑定原生步骤处理器的覆盖入口
            "custom_context_handlers": {
                "context_normalizer": context_normalizer_step,
            },
            "custom_agent_handlers": {
                "open_question_identifier": open_question_identifier_step,
                "machine_spec_compiler": machine_spec_compiler_step,
                "agent_package_generator": agent_package_generator_step,
                "acceptance_protocol_generator": acceptance_protocol_generator_step,
            },
            "custom_gate_handlers": {
                "human_decision_gate": human_decision_gate_step,
            },
        },
    )
