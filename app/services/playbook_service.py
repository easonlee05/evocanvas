"""面向 EvoCanvas WorkItem 的剧本执行与管理服务（PlaybookService）。

本服务模块提供有向无环图（TaskDAG）的多节点调度以及数据黑板（Blackboard）的状态共享机制。
"""
from __future__ import annotations

from typing import Dict, Any, Optional
from app.core.work import WorkItem, WorkStatus
from app.core.playbook import Playbook
from app.core.dag import TaskDAG, NodeStatus, DAGNode
from app.core.blackboard import Blackboard


class PlaybookService:
    """剧本执行与 DAG 调度服务类。

    管理处于运行态的 TaskDAG 与 Blackboard 实例，推动工作项（WorkItem）在各个剧本步骤的生命周期演进。
    """

    def __init__(self, storage: Any = None, llm: Any = None):
        """初始化 PlaybookService 实例。

        Args:
            storage: 持久化底座存储适配器。
            llm: 用于节点中大模型协作调用的 LLM 端口实例。
        """
        self.storage = storage
        self.llm = llm
        self.active_dags: Dict[str, TaskDAG] = {}
        self.blackboards: Dict[str, Blackboard] = {}

    def start_playbook(self, work_item: WorkItem, playbook: Playbook) -> None:
        """为指定的 native 工作项初始化 DAG 任务图，并启动剧本执行。

        将 Playbook 的步骤转换为 TaskDAG 节点，初始化黑板环境，并向黑板写入输入上下文指针，
        最后将工作项状态更新为 RUNNING 并持久化。

        Args:
            work_item: 被执行的工作项实体。
            playbook: 定义具体流程步骤的 Playbook 实体。
        """
        dag = TaskDAG(graph_id=work_item.work_id)
        
        # 兼容性适配：将 Playbook 固定的步骤配置转化为有向无环图的 DAGNode 节点
        for step in playbook.steps:
            node = DAGNode(
                node_id=step.step_id,
                action_type="agent",
                dependencies=[],
            )
            dag.add_node(node)
            
        self.active_dags[work_item.work_id] = dag
        self.blackboards[work_item.work_id] = Blackboard()
        
        # 将工作项中持有的核心 product_context 指针写入黑板，作为系统基础全局上下文
        self.blackboards[work_item.work_id].write("input_context_ref", work_item.product_context_ref, owner_node="system")
        work_item.status = WorkStatus.RUNNING
        
        if self.storage:
            self.storage.save_work(work_item)

    def run_next(self, work_id: str) -> None:
        """调度并执行 DAG 任务图中的下一个可运行节点。

        自动查询并提取 TaskDAG 中依赖项已满足且可以开始执行的节点。
        对于常规节点执行，向黑板写入对应的节点产出，并更新其状态为 COMPLETED；
        对于决策门（gate）节点，则维持挂起并等待用户裁决或输入。

        Args:
            work_id: 工作项的唯一标识符（即 DAG 图 ID）。
        """
        dag = self.active_dags.get(work_id)
        if not dag:
            return
            
        blackboard = self.blackboards.get(work_id)
        
        # 从 DAG 中抓取依赖已经全部解除（满足运行条件）的节点
        ready_nodes = dag.get_executable_nodes()
        for node in ready_nodes:
            node.status = NodeStatus.RUNNING
            
            # TODO: 后续需基于 ToolPolicy 白名单和真实 action_type 接入底层实际执行代理
            # 当前模拟阶段：常规节点自动跑通并写入黑板，决策门（gate）则挂起等待人工干预
            if node.action_type == "gate":
                # 决策门节点：挂起等待人工交互，此处暂不做状态流转
                pass
            else:
                node.result = f"Output of {node.node_id}"
                node.status = NodeStatus.COMPLETED
                
                if blackboard:
                    blackboard.write(f"{node.node_id}_result", node.result, owner_node=node.node_id)
                    
        if dag.is_completed():
            # 剧本中所有 DAG 节点均已执行完毕
            pass
