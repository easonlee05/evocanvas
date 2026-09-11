"""EvoCanvas MCP 协议工具能力集定义。

该模块通过 MCP 协议暴露各种业务管理与控制功能（如意图编译、规则提取、任务决策、AI 技术同事协作包打包、上下文局部检索等），
支持 AI 技术同事通过工具调用形式触发 EvoCanvas 核心工作流。
"""
import os
import json
from typing import List, Optional


def get_service():
    """按需实例化并获取后台 CLI 单例环境下的 TaskService 实例。

    工作目录可以通过环境变量 `EVOCANVAS_WORKSPACE` 指定，默认为当前进程目录。

    Returns:
        TaskService: 实例化的任务管理服务。
    """
    from app.cli.commands import build_cli_task_service
    output_dir = os.environ.get("EVOCANVAS_WORKSPACE", os.getcwd())
    return build_cli_task_service(output_dir)


def register_tools(mcp):
    """向给定的 FastMCP 实例注册所有核心控制层工具能力。

    Args:
        mcp: FastMCP 服务器实例。
    """
    
    @mcp.tool()
    def get_project_context(task_id: str) -> str:
        """获取指定任务的完整多轮演进 ProductContext（包含目标、需求、决策列表）。

        Args:
            task_id (str): 任务的唯一标识。

        Returns:
            str: 格式化后的 JSON 上下文信息，如发生错误则返回错误描述。
        """
        svc = get_service()
        try:
            ctx = svc.get_product_context(task_id)
            return json.dumps({
                "objective": ctx.objective,
                "requirements": [r.to_dict() for r in ctx.requirements],
                "decisions": [d.to_dict() for d in ctx.user_decisions]
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def query_context_fragment(task_id: str, section: str) -> str:
        """分片段精准查询任务的 ProductContext。

        Args:
            task_id (str): 任务的唯一标识。
            section (str): 查询的段落，仅限于 'objective'（目标）、'requirements'（需求）或 'decisions'（决策）。

        Returns:
            str: 包含特定段落数据的 JSON 序列化字符串。
        """
        svc = get_service()
        try:
            ctx = svc.get_product_context(task_id)
            if section == "objective":
                return json.dumps({"objective": ctx.objective}, ensure_ascii=False)
            elif section == "requirements":
                return json.dumps({"requirements": [r.to_dict() for r in ctx.requirements]}, ensure_ascii=False)
            elif section == "decisions":
                return json.dumps({"decisions": [d.to_dict() for d in ctx.user_decisions]}, ensure_ascii=False)
            else:
                return f"Error: Unknown section '{section}'. Use 'objective', 'requirements', or 'decisions'."
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def query_artifact_graph(task_id: str, node_id: str) -> str:
        """根据节点 ID 精准检索产物图（ArtifactGraph）中特定节点的信息与依赖关联。

        Args:
            task_id (str): 任务的唯一标识。
            node_id (str): 需要查询的产物节点 ID。

        Returns:
            str: 包含节点详情和依赖项的 JSON 格式数据。
        """
        svc = get_service()
        try:
            graph = svc.get_artifact_graph(task_id)
            node = next((n for n in graph.nodes if n.node_id == node_id), None)
            if not node:
                return f"Node {node_id} not found."
            deps = [e.to_dict() for e in graph.edges if e.from_node_id == node_id or e.to_node_id == node_id]
            return json.dumps({"node": node.to_dict(), "dependencies": deps}, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def diff_artifacts(task_id: str, artifact_id_1: str, artifact_id_2: str) -> str:
        """比对同一个任务中两个不同版本/ID 产物内容的差异。

        Args:
            task_id (str): 任务的唯一标识。
            artifact_id_1 (str): 待比对的第一个产物版本 ID。
            artifact_id_2 (str): 待比对的第二个产物版本 ID。

        Returns:
            str: 拼接两个产物内容纯文本的伪 Diff 视图。
        """
        svc = get_service()
        try:
            a1 = svc.storage.read_artifact(artifact_id_1)
            a2 = svc.storage.read_artifact(artifact_id_2)
            return f"--- {a1.name} (v{a1.version})\n+++ {a2.name} (v{a2.version})\n[Content 1]:\n{a1.content}\n[Content 2]:\n{a2.content}"
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def search_context(task_id: str, keyword: str) -> str:
        """通过关键词快速检索 ProductContext 中包含的内容，免于一次性加载全量庞大文本。

        Args:
            task_id (str): 任务的唯一标识。
            keyword (str): 检索的关键词。

        Returns:
            str: 匹配行合并后的文本；如无匹配项则返回相应提示。
        """
        svc = get_service()
        try:
            ctx = svc.get_product_context(task_id)
            results = []
            if keyword.lower() in ctx.objective.lower():
                results.append(f"Objective match: {ctx.objective}")
            for req in ctx.requirements:
                if keyword.lower() in req.statement.lower():
                    results.append(f"Requirement match: {req.statement}")
            for d in ctx.user_decisions:
                if keyword.lower() in (d.decision or "").lower() or keyword.lower() in (d.question or "").lower():
                    results.append(f"Decision match: {d.question} -> {d.decision}")
            return "\n".join(results) if results else "No matches found."
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def compile_spec(intent: str, material_ids: Optional[List[str]] = None) -> str:
        """将用户的业务意图快捷编译为 machine_spec.yaml 以及 human_brief.md，并异步启动对应编译处理任务。

        Args:
            intent (str): 核心业务意图/提示。
            material_ids (Optional[List[str]]): 依赖的相关参考文档元数据标识列表。

        Returns:
            str: 创建成功的任务状态提示，包含新的任务 ID。
        """
        svc = get_service()
        payload = {
            "username": "mcp_worker",
            "business_intent": intent,
            "material_ids": material_ids or []
        }
        try:
            task = svc.create_task("spec_to_agent", payload)
            svc.run_task(task.task_id)
            return f"Task created and started. Task ID: {task.task_id}. Please check status or context later."
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def request_decision(task_id: str, decision_text: str) -> str:
        """快捷向处于暂停挂起（如 DecisionGate 裁决门神）状态的 PM 工作流应用一项决策选择并继续跑任务。

        Args:
            task_id (str): 任务的唯一标识。
            decision_text (str): 最终确认的决策文本。

        Returns:
            str: 提交裁决后的最新任务状态。
        """
        svc = get_service()
        try:
            task = svc.apply_decision(task_id, decision=decision_text)
            svc.run_task(task.task_id)
            return f"Decision applied. Task status is now {task.status.value}."
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def get_agent_package(spec_path: str, output_path: str) -> str:
        """根据指定的 machine_spec.yaml 自动编译并打包生成 agent_package.md，交接 AI 技术同事。

        Args:
            spec_path (str): 机器规范文件的输入绝对路径。
            output_path (str): 打包生成结果的输出保存绝对路径。

        Returns:
            str: 打包成败提示。
        """
        from app.cli.commands import package_cmd
        try:
            package_cmd(spec_path, output_path, fake=False)
            return f"Package successfully written to {output_path}."
        except SystemExit:
            return "Package generation failed. Check server logs."
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def get_acceptance(spec_path: str, output_path: str) -> str:
        """根据指定的 machine_spec.yaml 自动编译并生成验收约束协议文件 acceptance.md。

        Args:
            spec_path (str): 机器规范文件的输入绝对路径。
            output_path (str): 验收协议结果的输出保存绝对路径。

        Returns:
            str: 验收生成成败提示。
        """
        from app.cli.commands import acceptance_cmd
        try:
            acceptance_cmd(spec_path, output_path, fake=False)
            return f"Acceptance protocol successfully written to {output_path}."
        except SystemExit:
            return "Acceptance generation failed."
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def create_requirement(task_id: str, statement: str) -> str:
        """快捷向当前任务上下文手动追加一条特定需求。

        Args:
            task_id (str): 任务的唯一标识。
            statement (str): 追加的需求陈述内容。

        Returns:
            str: 追加成功提示与新生成的需求 ID。
        """
        svc = get_service()
        try:
            ctx = svc.get_product_context(task_id)
            import uuid
            new_id = f"req_{uuid.uuid4().hex[:6]}"
            from app.core.playbook import Requirement
            ctx.requirements.append(Requirement(requirement_id=new_id, statement=statement))
            return f"Requirement {new_id} added successfully."
        except Exception as e:
            return f"Error: {e}"
