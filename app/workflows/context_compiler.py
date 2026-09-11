"""EvoCanvas 工作流上下文与结构化产物渲染服务。

`ContextCompilerService` 将工作流上下文编译为 EvoCanvas 可追溯的结构化产物，
包括机器规范、人类简报、AI 协作包、验收材料以及按任务声明生成的文档视图。
辅助任务输入只在边界内被转换，不参与当前产品事实和治理判断。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from app.core.errors import DomainError
from app.core.task import Task, WorkflowStep

try:
    from app.workflows.acceptance_review import render_review_result_artifact
except ModuleNotFoundError:
    def render_review_result_artifact(task: Task) -> str:
        raise DomainError(
            "workflow.compatibility_renderer_missing",
            "review_result renderer is unavailable in the current EvoCanvas runtime.",
        )


class ContextCompilerService:
    """上下文与产物渲染服务。

    该服务实现数据层表达，负责接收 Task 实例，渲染输出为标准的 markdown 或 YAML 文本格式。
    """

    def artifact_payload(self, task: Task, step: WorkflowStep) -> tuple[str, str]:
        """获取需要落盘的产物文件名与对应的文本内容。

        根据任务声明选择 EvoCanvas 结构化产物渲染器；辅助任务只作为输入适配。

        Args:
            task (Task): 任务实例。
            step (WorkflowStep): 产物步骤定义。

        Returns:
            tuple[str, str]: (产物文件名称, 渲染出的文本内容)
        """
        if task.definition.output_spec and step.output_keys:
            return self.structured_artifact_payload(task, step)

        output = task.context.step_outputs.get(
            "writer_final_prd" if task.definition.type == "prd" else "writer_scene_docs",
            {},
        )
        if output.get("artifact_name") and output.get("artifact_content"):
            return output["artifact_name"], output["artifact_content"]
        if task.definition.type == "prd":
            return "PRD.md", self.render_prd(task)
        return "模块概览.md", self.render_manual(task)

    def structured_artifact_payload(self, task: Task, step: WorkflowStep) -> tuple[str, str]:
        """渲染 EvoCanvas 结构化产物的元数据与内容。

        验证步骤声明并匹配注册的特定渲染器。

        Args:
            task (Task): 任务实例。
            step (WorkflowStep): 步骤定义。

        Returns:
            tuple[str, str]: (产物文件名称, 渲染出的文本内容)

        Raises:
            DomainError: 当产物契约或渲染器未定义时抛出。
        """
        if len(step.output_keys) != 1:
            raise DomainError(
                "workflow.structured_artifact_contract_invalid",
                f"Structured artifact step {step.id} must declare exactly one output_key.",
            )
        artifact_key = step.output_keys[0]
        artifact_name = task.definition.output_spec.get(artifact_key)
        if not artifact_name:
            raise DomainError(
                "workflow.structured_artifact_contract_missing_name",
                f"Structured artifact key {artifact_key} is missing from output_spec for {task.definition.type}.",
            )
        renderers = {
            "machine_spec": self.render_machine_spec,
            "human_brief": self.render_human_brief,
            "agent_package": self.render_agent_package,
            "acceptance": self.render_acceptance,
            "review_checklist": self.render_review_checklist,
            "traceability": self.render_traceability,
            "review_result": render_review_result_artifact,
        }
        renderer = renderers.get(artifact_key)
        if not renderer:
            raise DomainError(
                "workflow.structured_artifact_renderer_missing",
                f"No EvoCanvas renderer registered for artifact key {artifact_key}.",
            )
        return artifact_name, renderer(task)

    def render_prd(self, task: Task) -> str:
        """为需要文档视图的 EvoCanvas 工作项渲染产品需求文档 (PRD.md)。

        Args:
            task (Task): 任务对象。

        Returns:
            str: 渲染完成的 Markdown 文本。
        """
        decisions = "\n".join(f"- {item.decision}" for item in task.context.user_decisions) or "- 暂无用户裁决"
        evidence = self._extract_prd_evidence(task)
        is_points_gateway = "积分" in task.context.title or "积分" in task.context.goal
        roles = evidence["roles"] or (["用户", "风控运营", "客服", "审计"] if is_points_gateway else ["用户", "业务运营", "客服", "管理员"])
        scenarios = evidence["scenarios"] or (["签到", "下单返积分", "退款", "邀请"] if is_points_gateway else ["创建请求", "处理流转", "状态通知", "结果追踪"])
        problems = evidence["problems"] or (["异常积分套利", "积分损失", "风险识别滞后"] if is_points_gateway else ["流程效率不足", "状态不透明", "人工处理成本高"])
        constraints = task.context.user_constraints or ["不重构积分系统", "在积分入账前完成风险处置", "保留人工审核与追溯能力"]
        primary_action = "在积分入账前完成风险识别、拦截、延迟入账或转人工审核" if is_points_gateway else f"围绕“{task.context.goal}”建立可执行的业务闭环"
        risk_action = "降低异常积分套利和营销活动资金损失" if is_points_gateway else "降低人工协作成本并提升处理效率"
        trace_action = "为风控运营、客服和审计提供可解释的处置记录" if is_points_gateway else "为业务运营、客服和管理员提供可追溯的过程记录"
        entry_requirement = "支持签到、下单返积分、活动抽奖和邀请奖励等积分来源接入统一校验" if is_points_gateway else "支持核心业务请求的创建、受理、流转、通知和关闭"
        identify_requirement = "按用户 ID、设备 ID、IP、活动 ID、订单 ID 和邀请关系聚合风险特征" if is_points_gateway else "按用户、业务对象、处理节点、优先级和状态聚合任务上下文"
        action_requirement = "支持放行、拦截、延迟入账、人工审核和命中原因回传" if is_points_gateway else "支持提交、分派、升级、驳回、完成和结果回传"
        rule_requirements = [
            "频次规则：识别短时间高频签到、批量请求和异常设备聚集。",
            "订单规则：识别小号下单返积分、退款后保留积分和异常订单链路。",
            "邀请规则：识别邀请链路作假、循环邀请 and 同设备多账号邀请。",
            "策略配置：支持按活动、渠道和用户分层配置阈值、灰度比例和白名单。",
        ] if is_points_gateway else [
            "流转规则：按业务类型、优先级和处理时限分派任务。",
            "升级规则：识别超时、重复提交和高优先级请求并自动升级。",
            "权限规则：按角色控制查看、处理、驳回和关闭权限。",
            "配置能力：支持按业务线、渠道和用户分层配置流程规则。",
        ]
        metrics = "风险命中率、拦截金额、误杀率、人工审核通过率、客诉率和接口耗时" if is_points_gateway else "处理时长、按时完成率、升级率、驳回率、用户满意度和通知到达率"
        problem_statement = self._problem_statement(task, problems, is_points_gateway)
        return f"""# {task.context.title} PRD

## 1. 背景与问题定义
{task.context.title} {problem_statement}当前主要问题包括：{self._join_cn(problems)}。

## 2. 业务目标与非目标
### 业务目标
- {primary_action}。
- {risk_action}。
- {trace_action}。

### 非目标
- 首期不重构积分账户、结算或营销活动系统。
- 首期不建设通用风控中台，只交付积分场景网关能力。
- 首期不自动封禁用户账号，账号处置由现有风控或人工流程完成。

## 3. 用户角色与使用场景
- 目标角色：{self._join_cn(roles)}。
- 覆盖场景：{self._join_cn(scenarios)}。
- 典型链路：请求进入系统后，系统校验用户、业务对象、来源渠道和上下文，输出处理结果并沉淀审计记录。

## 4. 功能需求
- 请求接入：{entry_requirement}。
- 识别处理：{identify_requirement}。
- 处置动作：{action_requirement}。
- 审核闭环：人工审核结果可回写，用于后续规则优化和客诉解释。
- 可追溯记录：每次风险判断必须记录请求摘要、命中规则、处置动作和操作者。

## 5. 风控策略与规则
{chr(10).join(f"- {item}" for item in rule_requirements)}

## 6. 数据与指标
- 核心指标：{metrics}。
- 数据埋点：记录来源场景、风险等级、规则编号、处置动作、审核结论和最终积分状态。
- 看板需求：按日、活动、渠道、规则和处置动作查看风险趋势。

## 7. 异常流程与降级
- 规则服务不可用时按配置降级为延迟入账或放行并标记待复核。
- 外部依赖超时时返回明确降级原因，不得重复发放积分。
- 发现规则误杀时支持批量回滚处置结果并生成审计记录。
- 约束条件：{self._join_cn(constraints)}。

## 8. 验收标准
- 所有接入场景均能返回风险等级、处置动作和可解释命中原因。
- 命中高风险请求时，积分不得直接入账。
- 人工审核、回滚和审计链路可追溯到单次请求。
- PRD 评审记录覆盖 PM、Tech、QA 和 Reviewer 的结论。

## 9. 用户裁决
{decisions}
"""

    def render_manual(self, task: Task) -> str:
        """为 EvoCanvas 工作项渲染模块操作手册视图。

        Args:
            task (Task): 任务对象。

        Returns:
            str: 渲染完成的 Markdown 文本。
        """
        return f"# {task.context.title} 操作手册\n\n## 模块目标\n{task.context.goal}\n\n## 操作路径\n- 按用户材料和平台知识补全。\n"

    def render_machine_spec(self, task: Task) -> str:
        """渲染 EvoCanvas 的核心机器可读规范文件（machine_spec.yaml）。

        该文件是整个数字产品生命周期中的单事实来源（Source of Truth）。

        Args:
            task (Task): 任务对象。

        Returns:
            str: YAML 格式的规约文本内容。
        """
        business_intent = task.context.inputs.get("business_intent") or task.context.goal
        constraints = task.context.user_constraints or ["none"]
        compiler_structured = dict(task.context.step_outputs.get("machine_spec_compiler", {}).get("structured", {}))
        protocol_structured = dict(task.context.step_outputs.get("acceptance_protocol_generator", {}).get("structured", {}))
        context_normalizer_outputs = dict(task.context.step_outputs.get("context_normalizer", {}))
        return "\n".join(
            [
                "# source of truth: machine_spec",
                f"work_id: {task.task_id}",
                f"title: {json.dumps(task.context.title, ensure_ascii=False)}",
                f"objective: {json.dumps(task.context.goal, ensure_ascii=False)}",
                f"business_intent: {json.dumps(business_intent, ensure_ascii=False)}",
                "requirements:",
                "  - id: req_primary",
                f"    statement: {json.dumps(str(business_intent), ensure_ascii=False)}",
                "constraints:",
                *[f"  - {json.dumps(str(item), ensure_ascii=False)}" for item in constraints],
                f"compiled_contracts: {json.dumps(compiler_structured.get('strict_contracts', []), ensure_ascii=False)}",
                "acceptance_inputs:",
                *[
                    f"  - {json.dumps(str(item), ensure_ascii=False)}"
                    for item in protocol_structured.get("test_vectors", [])
                ],
                "playbook_context:",
                f"  source_of_truth: {json.dumps(str(compiler_structured.get('source_of_truth', 'machine_spec')), ensure_ascii=False)}",
                f"  context_scope: {json.dumps(str(context_normalizer_outputs.get('context_scope', 'default')), ensure_ascii=False)}",
            ]
        ) + "\n"

    def render_human_brief(self, task: Task) -> str:
        """渲染生成面向干系人阅读的人类简报文件（human_brief.md）。

        Args:
            task (Task): 任务对象。

        Returns:
            str: 简报文档文本。
        """
        return (
            f"# Human Brief\n\n"
            f"## Title\n{task.context.title}\n\n"
            f"## Objective\n{task.context.goal}\n\n"
            f"## Business Intent\n{task.context.inputs.get('business_intent', task.context.goal)}\n"
        )

    def render_agent_package(self, task: Task) -> str:
        """渲染生成供 AI 技术同事（如 Codex 等）执行的任务包描述（agent_package_codex.md）。

        Args:
            task (Task): 任务对象。

        Returns:
            str: 执行包文档内容。
        """
        return (
            f"# Agent Package For AI Technical Peer\n\n"
            f"- Work ID: {task.task_id}\n"
            f"- Source of Truth: `machine_spec.yaml`\n"
            f"- Objective: {task.context.goal}\n"
            f"- Primary Requirement: {task.context.inputs.get('business_intent', task.context.goal)}\n"
        )

    def render_acceptance(self, task: Task) -> str:
        """根据验收协议生成步骤的输出，渲染验收协议文档（acceptance.md）。

        Args:
            task (Task): 任务对象。

        Returns:
            str: 验收协议文档内容。
        """
        protocol_structured = dict(task.context.step_outputs.get("acceptance_protocol_generator", {}).get("structured", {}))
        acceptance_inputs = protocol_structured.get("test_vectors", [])
        acceptance_lines = "".join(f"- {item}\n" for item in acceptance_inputs)
        return (
            f"# Acceptance Protocol\n\n"
            f"## Required Outcome\n{task.context.goal}\n\n"
            f"## Checks\n"
            f"- Machine spec can be traced to the stated business intent.\n"
            f"- Agent package stays aligned with the machine spec.\n"
            f"- Reviewer can validate the delivered work against this protocol.\n"
            f"{acceptance_lines}"
        )

    def render_review_checklist(self, task: Task) -> str:
        """渲染交付产物评审检查清单（review_checklist.md）。

        Args:
            task (Task): 任务对象。

        Returns:
            str: 检查清单文档文本。
        """
        return (
            f"# Review Checklist\n\n"
            f"- [ ] `machine_spec.yaml` reflects `{task.context.inputs.get('business_intent', task.context.goal)}`.\n"
            f"- [ ] `human_brief.md` is readable by stakeholders.\n"
            f"- [ ] `agent_package_codex.md` is executable by AI technical peers.\n"
            f"- [ ] `acceptance.md` defines clear pass/fail checks.\n"
            f"- [ ] `traceability.json` anchors outputs back to `req_primary`.\n"
        )

    def render_traceability(self, task: Task) -> str:
        payload = {
            "work_id": task.task_id,
            "source_of_truth": "machine_spec.yaml",
            "requirements": [
                {
                    "requirement_id": "req_primary",
                    "statement": task.context.inputs.get("business_intent", task.context.goal),
                    "artifacts": [
                        "machine_spec.yaml",
                        "human_brief.md",
                        "agent_package_codex.md",
                        "acceptance.md",
                        "review_checklist.md",
                    ],
                }
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _extract_prd_evidence(self, task: Task) -> Dict[str, List[str]]:
        source = "\n".join(
            str(value)
            for value in [task.context.title, task.context.goal, task.context.inputs.get("prompt", "")]
            if value
        )
        candidates = {
            "problems": ["签到脚本", "小号下单返积分", "退款套利", "邀请作弊", "异常积分套利", "积分损失"],
            "roles": ["用户", "风控运营", "客服", "审计"],
            "scenarios": ["签到", "下单返积分", "活动抽奖", "邀请奖励", "退款"],
        }
        return {key: [item for item in values if item in source] for key, values in candidates.items()}

    @staticmethod
    def _join_cn(items: List[str]) -> str:
        return "、".join(items)

    @staticmethod
    def _problem_statement(task: Task, problems: List[str], is_points_gateway: bool) -> str:
        if is_points_gateway:
            return "面向电商积分链路，在积分入账前识别并处置作弊风险。"
        return f"围绕“{task.context.goal}”建立清晰、可追踪、可验收的产品能力。"
