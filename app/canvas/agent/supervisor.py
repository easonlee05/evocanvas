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

        prompt = f"""你是 EvoCanvas 的意图路由 Supervisor。你的唯一职责是分析用户输入，判断意图类型，并规划需要激活的协作角色。

# 可用角色及职责

- InputCompiler: 接收新输入，编译多源材料（会议纪要、聊天、需求文档），提取证据卡和问题定义卡。
- Clarifier: 发现歧义、缺失信息与冲突，提出待澄清卡。
- ConstraintSteward: 沉淀稳定业务规则、术语、数据口径等约束卡。
- DecisionSteward: 识别必须由 PM 拍板的待决策卡。
- OptionBuilder: 接收方案建议并生成方案候选卡。
- HandoffBuilder: 编写与收束结构化交接物草稿卡。

# 路由决策规则（按优先级顺序判断）

1. 有新材料输入时（用户粘贴了文本、上传了文件、引入了参考数据）：
   必须路由到 input_compilation + InputCompiler。
   如果材料中同时存在分歧或不确定性，追加 clarification + Clarifier。

2. 用户在追问或质疑已有内容时（"为什么"、"不确定"、"这里有问题"）：
   路由到 clarification + Clarifier。

3. 用户在陈述规则、边界或约束条件时（"必须"、"不能"、"规定是"）：
   路由到 constraint + ConstraintSteward。

4. 用户面临方案选择或要求拍板时（"A 还是 B"、"你来决定"、"哪个更好"）：
   路由到 decision + DecisionSteward。

5. 用户在讨论或对比备选方案时（"如果…会怎样"、"对比一下"、"有什么选择"）：
   路由到 option + OptionBuilder。

6. 用户要求整理输出或生成交接物时（"整理成文档"、"输出 PRD"、"生成报告"）：
   路由到 handoff + HandoffBuilder。

7. 意图不明确时：默认路由到 input_compilation + InputCompiler。

# 约束

- NEVER 在有新背景输入时跳过 InputCompiler 直接路由到后续阶段。
- 混合意图用 "+" 连接（如 "input_compilation+clarification"），角色用列表。
- 不要返回任何解释，只返回 JSON。

# 当前输入

用户消息: "{message}"

工作区已选中的卡片: {workspace_context.get("selected_cards", [])}

新引入参考材料内容:
{materials_str}

# 输出格式

必须输出 JSON，不要包含 Markdown 标记或其他文字：
{{"intent": "意图标识", "roles": ["角色1", "角色2"]}}
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
            valid_roles = {"InputCompiler", "Clarifier", "ConstraintSteward", "DecisionSteward", "HandoffBuilder", "OptionBuilder"}
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
        material_ids = workspace_context.get("material_ids", [])
        source_ref_ids = workspace_context.get("source_ref_ids", [])

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

        # 2. 只要本轮带入了新资料或新数据引用，就必须先经过输入编译。
        if material_ids or source_ref_ids:
            if "input_compilation" not in matched_intents:
                matched_intents.insert(0, "input_compilation")
            if "InputCompiler" not in matched_roles:
                matched_roles.insert(0, "InputCompiler")

        # 2. 如果文本中未能匹配到任何非默认意图，尝试利用 workspace_context 推荐
        if not matched_intents:
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
                    elif kind == "option":
                        matched_intents.append("option")
                        matched_roles.append("OptionBuilder")
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
