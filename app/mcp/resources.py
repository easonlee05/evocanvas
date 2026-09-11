"""EvoCanvas MCP 资源注册定义。

本模块通过 MCP 协议向外部提供 EvoCanvas 的核心状态资源（如任务的产品上下文、生成的产物内容），
以便下游 AI Worker 直接检索和获取受控资源。
"""
import json
from app.mcp.tools import get_service


def register_resources(mcp):
    """在 MCP 服务实例上注册可供客户端拉取的资源端点。

    Args:
        mcp: FastMCP 应用程序实例。
    """
    
    @mcp.resource("task://{task_id}/context")
    def get_task_context(task_id: str) -> str:
        """获取指定任务的完整产品上下文 (ProductContext) 资源。

        包含任务的目标、需求列表以及用户的决策历史，序列化为 JSON 字符串返回。

        Args:
            task_id (str): 目标任务 ID。

        Returns:
            str: 格式化后的 JSON 上下文信息；若抛出异常则返回错误提示。
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
            # 捕获异常，防止 MCP 底层服务由于单次资源获取失败而中断
            return f"Error: {e}"

    @mcp.resource("task://{task_id}/artifact")
    def get_task_artifact(task_id: str) -> str:
        """获取指定任务的最新文档产物内容资源。

        Args:
            task_id (str): 目标任务 ID。

        Returns:
            str: 最新产物的 Markdown 文本内容；若未生成则返回提示。
        """
        svc = get_service()
        try:
            artifacts = svc.storage.list_artifacts(task_id)
            if not artifacts:
                return "No artifacts generated yet."
            # 获取版本最先进的最新交付文档
            latest = artifacts[-1]
            full = svc.storage.read_artifact(latest.artifact_id)
            return full.content or ""
        except Exception as e:
            return f"Error: {e}"
