"""工作流步骤的重试、超时及熔断策略运行时计算模块。

该模块根据步骤定义的重试策略配置，在发生执行故障时进行确定性的决策计算（如是否重试、延迟多久等），
但其自身不执行实际的挂起或延时操作（即无阻塞）。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from app.core.task import WorkflowStep


class RetryDecision(str, Enum):
    """重试判定决策结果枚举。"""

    # 允许重试
    RETRY = "retry"
    # 放弃，达到最大重试上限
    GIVE_UP = "give_up"
    # 超时，执行用时已超出步骤配置的阈值
    TIMEOUT = "timeout"
    # 熔断开启，遇到显式声明不进行重试的特定错误码
    CIRCUIT_OPEN = "circuit_open"


@dataclass(frozen=True)
class RetryPolicyDecision:
    """封装了一次具体的重试评估决策的数据类。"""

    decision: RetryDecision
    step_id: str
    attempt: int
    next_attempt: int
    max_attempts: int
    delay_seconds: float
    reason: str
    error_code: Optional[str] = None

    @property
    def should_retry(self) -> bool:
        """检查当前的决策是否支持进行重试操作。

        Returns:
            bool: 如果决策结果为 RETRY 则返回 True，否则返回 False。
        """
        return self.decision == RetryDecision.RETRY


@dataclass
class RetryPolicyRuntime:
    """重试策略计算运行时。

    负责对 `WorkflowStep.retry_policy` 进行解析，结合当前已重试次数、消耗时间及错误码，
    计算下一步应该采取的动作。
    """

    default_max_attempts: int = 1
    default_backoff_seconds: float = 0
    default_timeout_ms: Optional[int] = None

    def evaluate(
        self,
        step: WorkflowStep,
        *,
        attempt: int,
        elapsed_ms: int,
        error_code: Optional[str] = None,
    ) -> RetryPolicyDecision:
        """评估指定步骤当前尝试失败后的重试策略。

        Args:
            step (WorkflowStep): 正在评估的工作流步骤实例。
            attempt (int): 当前已完成的尝试次数（从 1 开始计）。
            elapsed_ms (int): 当前步骤自开始执行以来已消耗的毫秒数。
            error_code (Optional[str], optional): 导致的错误码标识。默认为 None。

        Returns:
            RetryPolicyDecision: 生成的确定性重试决策。
        """
        policy = dict(step.retry_policy or {})
        
        # 提取最大尝试次数。支持 max_attempts 或 legacy retries 配置
        max_attempts = int(policy.get("max_attempts", policy.get("retries", self.default_max_attempts)))
        if "retries" in policy and "max_attempts" not in policy:
            max_attempts = int(policy["retries"]) + 1
            
        # 1. 检查是否超时
        timeout_ms = policy.get("timeout_ms", self.default_timeout_ms)
        if timeout_ms is not None and elapsed_ms > int(timeout_ms):
            return self._decision(RetryDecision.TIMEOUT, step, attempt, max_attempts, 0, "timeout_exceeded", error_code)

        # 2. 检查是否为不可重试的熔断错误
        non_retryable = {str(item) for item in policy.get("non_retryable_errors", [])}
        if error_code and error_code in non_retryable:
            return self._decision(RetryDecision.CIRCUIT_OPEN, step, attempt, max_attempts, 0, "non_retryable_error", error_code)

        # 3. 检查是否已达到最大重试次数上限
        if attempt >= max_attempts:
            return self._decision(RetryDecision.GIVE_UP, step, attempt, max_attempts, 0, "max_attempts_exhausted", error_code)

        # 4. 计算重试延迟并返回重试决策
        delay = self._delay_seconds(policy, attempt)
        return self._decision(RetryDecision.RETRY, step, attempt, max_attempts, delay, "retry_allowed", error_code)

    def _delay_seconds(self, policy: Dict[str, Any], attempt: int) -> float:
        """根据策略配置计算当前重试延迟的秒数。

        支持三种延迟退避策略：fixed (固定), linear (线性增长), exponential (指数退避)。

        Args:
            policy (Dict[str, Any]): 步骤重试策略字典。
            attempt (int): 已完成的尝试次数。

        Returns:
            float: 需要延迟等待的秒数。
        """
        base = float(policy.get("backoff_seconds", self.default_backoff_seconds))
        strategy = str(policy.get("backoff", policy.get("backoff_strategy", "fixed"))).lower()
        if strategy == "exponential":
            return base * (2 ** max(0, attempt - 1))
        if strategy == "linear":
            return base * max(1, attempt)
        return base

    @staticmethod
    def _decision(
        decision: RetryDecision,
        step: WorkflowStep,
        attempt: int,
        max_attempts: int,
        delay_seconds: float,
        reason: str,
        error_code: Optional[str],
    ) -> RetryPolicyDecision:
        """辅助方法，用于构造 RetryPolicyDecision 实例。"""
        return RetryPolicyDecision(
            decision=decision,
            step_id=step.id,
            attempt=attempt,
            next_attempt=attempt + 1,
            max_attempts=max_attempts,
            delay_seconds=delay_seconds,
            reason=reason,
            error_code=error_code,
        )

    def to_event_payload(
        self,
        step: WorkflowStep,
        decision: RetryPolicyDecision,
        *,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """将重试决策状态序列化为事件负载字典，便于分发或审计。

        Args:
            step (WorkflowStep): 当前工作流步骤。
            decision (RetryPolicyDecision): 已计算出的重试决策。
            error_message (Optional[str], optional): 选填的脱敏前的错误描述信息。默认为 None。

        Returns:
            Dict[str, Any]: 可用于日志或 SSE 事件的字典载荷。
        """
        return {
            "step_id": step.id,
            "step_type": step.type,
            "decision": decision.decision.value,
            "attempt": decision.attempt,
            "next_attempt": decision.next_attempt,
            "max_attempts": decision.max_attempts,
            "delay_seconds": decision.delay_seconds,
            "reason": decision.reason,
            "error_code": decision.error_code,
            "error_message_redacted": bool(error_message),
        }

