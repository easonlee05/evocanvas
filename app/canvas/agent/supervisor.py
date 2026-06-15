"""EvoCanvas Canvas Supervisor。

当前仅负责基于用户输入做意图识别与角色规划，
不承担实际 subagent 调度与 mutation 合并。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from app.canvas.agent.contracts import CanvasTurnPlan
from app.canvas.agent.roles import get_intent_routes, get_role


class CanvasSupervisor:
    """识别当前输入意图，并为单轮对话选择内部角色。"""

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    def recognize_and_plan(self, workspace_context: Dict[str, Any], message: str) -> CanvasTurnPlan:
        """根据消息内容和工作空间上下文生成角色规划。"""
        # 1. 检查是否为真实大模型运行环境 (非 FakeLLM，且 API 秘钥有效)
        from app.services.fakes import FakeLLM
        is_fake = (
            self.llm is None
            or isinstance(self.llm, FakeLLM)
            or getattr(self.llm, "api_key", "") == ""
        )

        if not is_fake:
            # 真实大模型调用，获取语义匹配的路由建议
            plan = self._recognize_and_plan_with_llm(workspace_context, message)
            if plan is not None:
                return plan

        # 2. 本地回退规则分支
        intent, roles = self._select_intent_and_roles_with_context(workspace_context, message)
        return CanvasTurnPlan(
            intent=intent,
            roles=roles,
            allowed_mutation_types=self._collect_allowed_mutation_types(roles),
        )

    def _recognize_and_plan_with_llm(
        self, workspace_context: Dict[str, Any], message: str
    ) -> CanvasTurnPlan | None:
        import re
        import json

        # 从全局内存缓存中水合材料具体内容，供大模型分析
        materials_content_list = []
        try:
            from app.api.server import global_materials_cache, global_source_refs_cache
            for mid in workspace_context.get("material_ids", []):
                if mid in global_materials_cache:
                    mat = global_materials_cache[mid]
                    materials_content_list.append(
                        f"--- 模拟材料文件: {mat['filename']} (ID: {mid}) ---\n{mat['content']}\n"
                    )
            for source_ref_id in workspace_context.get("source_ref_ids", []):
                if source_ref_id in global_source_refs_cache:
                    source_ref = global_source_refs_cache[source_ref_id]
                    snapshot = source_ref.get("snapshot", {})
                    materials_content_list.append(
                        f"--- 结构化数据引用: {source_ref.get('display_name', source_ref_id)} (ID: {source_ref_id}) ---\n"
                        f"{snapshot.get('summary', '暂无快照摘要')}\n"
                    )
        except Exception:
            pass
        materials_str = "\n".join(materials_content_list) if materials_content_list else "（无新引入材料内容）"

        prompt = f"""你是一个项目 Supervisor，负责识别用户的自然语言意图，并规划对应的协作角色。

主画布的备选协作角色及职责如下：
- "InputCompiler": 接收新输入，编译多源材料（如会议纪要、聊天），提取证据卡 (evidence)。
- "Clarifier": 发现歧义、缺失信息与冲突，提出待澄清卡 (clarification)。
- "ConstraintSteward": 沉淀稳定业务规则、术语、数据口径等约束卡 (constraint)。
- "DecisionSteward": 识别必须由 PM 拍板的待决策卡 (decision)。
- "HandoffBuilder": 编写与收束结构化交接物草稿卡 (handoff)。

用户当前的输入消息为: "{message}"

工作区已选中的卡片信息: {workspace_context.get("selected_cards", [])}
新引入参考材料具体内容如下:
{materials_str}


★ 特别路由规划原则：
1. 当用户输入了新的会议纪要、聊天记录或具体需求背景（包括用户直接输入的信息、以及新引入的参考材料内容），这属于多源输入编译阶段。你必须首先规划 "input_compilation" 意图并引入 "InputCompiler" 角色，以便对这些原始素材进行探索性提取（生成第 1 栏证据卡和第 2 栏问题定义卡）。
2. 如果你在这些新输入中进一步发现了各方观点的分歧、未知项或冲突，你应该同时规划 "clarification" 意图并引入 "Clarifier" 角色。此时应当输出混合意图路由 "input_compilation+clarification" 并指定角色 ["InputCompiler", "Clarifier"]。
3. 严禁在有新背景输入时忽略新材料的提取而直接越级路由到后续的单独澄清、约束或交接。确保新输入先在第 1、2 栏沉淀其事实证据与问题定义。

请进行意图路由，必须在以下几个备选意图里进行选择：
- "input_compilation": 包含新材料、聊天纪要输入编译。
- "clarification": 处理待澄清事项、暴露矛盾或不确定性。
- "constraint": 约束、规则或边界边界沉淀。
- "decision": 需要决策、方案取舍拍板的事项。
- "handoff": 整理或生成结构化交接物。

若用户的输入意图不明确，请根据选中的卡片类型或新材料做出推荐；若包含混合意图（如先澄清再交接），意图之间用 "+" 连接，角色使用英文逗号分隔。

你必须输出 JSON 格式的回复，结构如下：
{{
  "intent": "你的意图，例如：clarification+handoff",
  "roles": ["Clarifier", "HandoffBuilder"]
}}
请不要返回任何 Markdown 标记或多余解释。
"""
        try:
            # 调用真实的 llm.invoke
            result = self.llm.invoke(
                role="supervisor",
                prompt=prompt,
                context={
                    "title": "Intent Routing",
                    "goal": "Route user message to proper roles",
                    "model": workspace_context.get("model"),
                }
            )
            # 解析并提取 JSON 内容，过滤掉可能的 Markdown 包裹
            raw_content = result.content.strip()
            match = re.search(r"\{.*\}", raw_content, re.DOTALL)
            if match:
                raw_content = match.group(0)

            data = json.loads(raw_content)
            intent = data["intent"]
            roles = tuple(data["roles"])

            # 校验并提取合法的角色名称
            valid_roles = {"InputCompiler", "Clarifier", "ConstraintSteward", "DecisionSteward", "HandoffBuilder"}
            filtered_roles = tuple(r for r in roles if r in valid_roles)
            if not filtered_roles:
                return None

            return CanvasTurnPlan(
                intent=intent,
                roles=filtered_roles,
                allowed_mutation_types=self._collect_allowed_mutation_types(filtered_roles),
            )
        except Exception:
            # 捕获任何异常，返回 None 以触发 fallback 兜底
            return None

    def _select_intent_and_roles_with_context(self, workspace_context: Dict[str, Any], message: str) -> Tuple[str, Tuple[str, ...]]:
        normalized_message = message.strip()
        matched_intents: List[str] = []
        matched_roles: List[str] = []
        fallback_route = None

        # 1. 尝试使用文本匹配查找关键字意图
        for route in get_intent_routes():
            if not route.keywords:
                fallback_route = route
                continue
            if self._contains_any(normalized_message, list(route.keywords)):
                matched_intents.append(route.intent)
                for role_name in route.roles:
                    if role_name not in matched_roles:
                        matched_roles.append(role_name)

        # 2. 如果文本中未能匹配到任何非默认意图，尝试利用 workspace_context 推荐
        if not matched_intents:
            material_ids = workspace_context.get("material_ids", [])
            source_ref_ids = workspace_context.get("source_ref_ids", [])
            selected_cards = workspace_context.get("selected_cards", [])
            
            # 如果有新材料输入或新的结构化数据引用
            if material_ids or source_ref_ids:
                return "input_compilation", ("InputCompiler",)
            
            # 如果有选中卡片，且能提取出卡片 kind
            if selected_cards:
                kinds = {c.get("kind") for c in selected_cards if c.get("kind")}
                for kind in kinds:
                    if kind == "clarification":
                        matched_intents.append("clarification")
                        matched_roles.append("Clarifier")
                    elif kind == "constraint":
                        matched_intents.append("constraint")
                        matched_roles.append("ConstraintSteward")
                    elif kind == "decision":
                        matched_intents.append("decision")
                        matched_roles.append("DecisionSteward")
                    elif kind == "handoff":
                        matched_intents.append("handoff")
                        matched_roles.append("HandoffBuilder")
                    elif kind in ("evidence", "problem"):
                        matched_intents.append("clarification")
                        matched_roles.append("Clarifier")
                        
                # 剔除重复角色并保持顺序
                unique_roles = []
                for r in matched_roles:
                    if r not in unique_roles:
                        unique_roles.append(r)
                
                if matched_intents:
                    return "+".join(matched_intents), tuple(unique_roles)

        # 3. 回退默认意图
        if not matched_intents:
            if fallback_route is None:
                return "input_compilation", ("InputCompiler",)
            return fallback_route.intent, fallback_route.roles
            
        return "+".join(matched_intents), tuple(matched_roles)

    def _select_intent_and_roles(self, message: str) -> Tuple[str, Tuple[str, ...]]:
        normalized_message = message.strip()
        matched_intents: List[str] = []
        matched_roles: List[str] = []
        fallback_route = None

        for route in get_intent_routes():
            if not route.keywords:
                fallback_route = route
                continue
            if self._contains_any(normalized_message, list(route.keywords)):
                matched_intents.append(route.intent)
                for role_name in route.roles:
                    if role_name not in matched_roles:
                        matched_roles.append(role_name)

        if not matched_intents:
            if fallback_route is None:
                return "input_compilation", ("InputCompiler",)
            return fallback_route.intent, fallback_route.roles
        return "+".join(matched_intents), tuple(matched_roles)

    def _collect_allowed_mutation_types(self, roles: Iterable[str]) -> Tuple[str, ...]:
        allowed_mutation_types: List[str] = []
        for role_name in roles:
            for mutation_type in get_role(role_name).allowed_mutation_types:
                if mutation_type not in allowed_mutation_types:
                    allowed_mutation_types.append(mutation_type)
        return tuple(allowed_mutation_types)

    @staticmethod
    def _contains_any(message: str, keywords: List[str]) -> bool:
        return any(keyword in message for keyword in keywords)
