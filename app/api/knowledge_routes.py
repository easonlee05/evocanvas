"""EvoCanvas 知识库、外部来源连接器与历史兼容路由模块（从 server.py 拆分）。"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from fastapi import Body, Depends, FastAPI, HTTPException

from app.api.auth import RolePolicy, User
from app.api.schemas import KnowledgeCandidateCreateRequest, SourceRefCreateRequest
from app.services.task_service import TaskService


def register_knowledge_and_compat_routes(
    app: FastAPI,
    *,
    get_current_user: Callable[..., Any],
    get_task_service: Callable[..., Any],
    knowledge_items_provider: Callable[[], List[Dict[str, Any]]],
    rule_items_provider: Callable[[], List[Dict[str, Any]]],
    recycle_items_provider: Callable[[], List[Dict[str, Any]]],
    build_source_ref_summary: Callable[..., str],
    format_event_time: Callable[..., str],
    global_knowledge_candidates_cache: Dict[str, Dict[str, Any]],
    global_source_refs_cache: Dict[str, Dict[str, Any]],
) -> None:
    """向 FastAPI 应用注册知识库、来源引用与历史兼容接口。"""
    _knowledge_items = knowledge_items_provider
    _rule_items = rule_items_provider
    _recycle_items = recycle_items_provider
    _build_source_ref_summary = build_source_ref_summary
    _format_event_time = format_event_time

    @app.get("/api/knowledge")
    async def list_knowledge(
        user: User = Depends(get_current_user),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        RolePolicy.enforce(user.role, "knowledge.read")
        return {"items": _knowledge_items()}

    @app.post("/api/knowledge")
    async def create_knowledge(
        payload: Dict[str, Any] = Body(...),
        user: User = Depends(get_current_user),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        RolePolicy.enforce(user.role, "knowledge.write")
        item = {
            "id": f"kb_{uuid4().hex[:8]}",
            "type": payload.get("type", "doc"),
            "title": payload.get("title", "未命名知识"),
            "desc": payload.get("desc", "已提交到候选知识区，等待后续解析入库。"),
            "tags": payload.get("tags", []),
            "updated": "刚刚",
            "author": payload.get("author", "User"),
        }
        return item

    @app.get("/api/knowledge/candidates")
    async def list_knowledge_candidates(
        user: User = Depends(get_current_user),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        RolePolicy.enforce(user.role, "knowledge.read")
        del service
        return {"items": list(global_knowledge_candidates_cache.values())}

    @app.post("/api/knowledge/candidates")
    async def create_knowledge_candidate(
        payload: KnowledgeCandidateCreateRequest,
        user: User = Depends(get_current_user),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        RolePolicy.enforce(user.role, "knowledge.write")
        del service
        item = {
            "id": f"kbc_{uuid4().hex[:8]}",
            "type": payload.type or "doc",
            "title": payload.title,
            "desc": payload.desc or "来自工作区产出或资料抽取的候选知识，等待审核。",
            "tags": list(payload.tags or []),
            "author": payload.author or "Canvas AI",
            "status": "candidate",
            "updated": "刚刚",
            "source_artifact_id": payload.source_artifact_id,
            "source_workspace_id": payload.source_workspace_id,
        }
        global_knowledge_candidates_cache[item["id"]] = item
        return item

    @app.post("/api/knowledge/{knowledge_id}/approve")
    async def approve_knowledge(
        knowledge_id: str,
        payload: Optional[Dict[str, Any]] = Body(None),
        user: User = Depends(get_current_user),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        RolePolicy.enforce(user.role, "knowledge.write")
        del service
        candidate = global_knowledge_candidates_cache.get(knowledge_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="knowledge candidate not found")
        approved = {
            "id": f"kb_{uuid4().hex[:8]}",
            "type": payload.get("type", candidate.get("type", "doc")) if payload else candidate.get("type", "doc"),
            "title": (payload or {}).get("title", candidate.get("title", "未命名知识")),
            "desc": (payload or {}).get("desc", candidate.get("desc", "")),
            "tags": (payload or {}).get("tags", candidate.get("tags", [])),
            "updated": "刚刚",
            "author": candidate.get("author", "Canvas AI"),
            "status": "approved",
            "source_candidate_id": knowledge_id,
        }
        global_knowledge_candidates_cache.pop(knowledge_id, None)
        return approved

    @app.get("/api/source-connectors")
    async def list_source_connectors(
        user: User = Depends(get_current_user),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        RolePolicy.enforce(user.role, "material.read")
        del service
        return {
            "items": [
                {
                    "id": "saved_query",
                    "label": "保存查询",
                    "description": "引用已保存 SQL 或查询模版，生成受控快照后参与输入编译。",
                },
                {
                    "id": "dashboard_metric",
                    "label": "指标看板",
                    "description": "引用 BI 看板指标与筛选条件，生成可追溯的数据证据卡。",
                },
                {
                    "id": "table_slice",
                    "label": "数据切片",
                    "description": "对表或视图做有限条件切片，只返回样本和聚合摘要。",
                },
            ]
        }

    @app.get("/api/source-refs")
    async def list_source_refs(
        user: User = Depends(get_current_user),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        """列出当前已创建的外部数据引用。"""
        RolePolicy.enforce(user.role, "material.read")
        del service
        return {"items": list(global_source_refs_cache.values())}

    @app.post("/api/source-refs")
    async def create_source_ref(
        payload: SourceRefCreateRequest,
        user: User = Depends(get_current_user),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        """创建一个外部结构化数据引用，并生成首个只读快照摘要。"""
        RolePolicy.enforce(user.role, "material.upload")
        del service
        source_ref_id = f"src_{uuid4().hex[:10]}"
        snapshot_id = f"snapshot_{uuid4().hex[:10]}"
        summary = _build_source_ref_summary(
            connector_type=payload.connector_type,
            display_name=payload.display_name,
            query_text=payload.query_text,
            metric_name=payload.metric_name,
            filters=payload.filters,
        )
        item = {
            "source_ref_id": source_ref_id,
            "layer": "source_ref",
            "connector_type": payload.connector_type,
            "display_name": payload.display_name,
            "workspace_id": payload.workspace_id,
            "query_text": payload.query_text,
            "metric_name": payload.metric_name,
            "filters": dict(payload.filters or {}),
            "snapshot": {
                "snapshot_id": snapshot_id,
                "captured_at": "刚刚",
                "summary": summary,
                "sample_rows": [],
                "aggregates": [],
            },
        }
        global_source_refs_cache[source_ref_id] = item
        return item

    @app.get("/api/source-refs/{source_ref_id}")
    async def get_source_ref(
        source_ref_id: str,
        user: User = Depends(get_current_user),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        """读取指定数据引用及其最新快照摘要。"""
        RolePolicy.enforce(user.role, "material.read")
        del service
        item = global_source_refs_cache.get(source_ref_id)
        if not item:
            raise HTTPException(status_code=404, detail="source ref not found")
        return item

    @app.post("/api/source-refs/{source_ref_id}/snapshot")
    async def refresh_source_ref_snapshot(
        source_ref_id: str,
        payload: Optional[Dict[str, Any]] = Body(None),
        user: User = Depends(get_current_user),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        """显式刷新一个数据引用的只读快照。"""
        RolePolicy.enforce(user.role, "material.upload")
        del service
        item = global_source_refs_cache.get(source_ref_id)
        if not item:
            raise HTTPException(status_code=404, detail="source ref not found")
        snapshot_id = f"snapshot_{uuid4().hex[:10]}"
        filters = (payload or {}).get("filters", item.get("filters", {}))
        item["filters"] = dict(filters or {})
        item["snapshot"] = {
            "snapshot_id": snapshot_id,
            "captured_at": "刚刚",
            "summary": _build_source_ref_summary(
                connector_type=item.get("connector_type", "saved_query"),
                display_name=item.get("display_name", "未命名数据引用"),
                query_text=item.get("query_text"),
                metric_name=item.get("metric_name"),
                filters=item.get("filters", {}),
            ),
            "sample_rows": [],
            "aggregates": [],
        }
        return item

    @app.get("/api/rules")
    async def list_rules(
        status: str = "pending",
        user: User = Depends(get_current_user),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        """获取提取出的产品规则白名单/黑名单列表。"""
        RolePolicy.enforce(user.role, "knowledge.read")
        return {"rules": [rule for rule in _rule_items() if rule["status"] == status]}

    @app.post("/api/rules/{rule_id}/approve")
    async def approve_rule(
        rule_id: str,
        payload: Optional[Dict[str, Any]] = Body(None),
        user: User = Depends(get_current_user),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        RolePolicy.enforce(user.role, "knowledge.approve")
        p = payload or {}
        content = p.get("content") or p.get("desc") or p.get("title")
        return {"id": rule_id, "status": "approved", "content": content}

    @app.post("/api/rules/{rule_id}/reject")
    async def reject_rule(
        rule_id: str,
        user: User = Depends(get_current_user),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        RolePolicy.enforce(user.role, "knowledge.approve")
        return {"id": rule_id, "status": "rejected"}

    @app.get("/api/recycle")
    async def list_recycle(
        user: User = Depends(get_current_user),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        RolePolicy.enforce(user.role, "task.read")
        tasks = service.storage.list_tasks(service.registry)
        deleted_tasks = [t for t in tasks if getattr(t, "is_deleted", False)]
        items = []
        for t in deleted_tasks:
            import os
            task_file = service.storage._task_dir(t.task_id) / "task.json"
            size = "N/A"
            if task_file.exists():
                size_kb = os.path.getsize(task_file) / 1024
                size = f"{size_kb:.1f} KB"
            items.append({
                "id": t.task_id,
                "name": t.context.title,
                "type": "task",
                "size": size,
                "deletedAt": _format_event_time(t.deleted_at) if getattr(t, "deleted_at", None) else "刚刚",
                "deletedBy": "User"
            })
        return {"items": items + _recycle_items()}

    @app.post("/api/recycle/{item_id}/restore")
    async def restore_recycle(
        item_id: str,
        user: User = Depends(get_current_user),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        RolePolicy.enforce(user.role, "task.write")
        if item_id.startswith("trash_"):
            return {"id": item_id, "status": "restored"}
        try:
            service.restore_task(item_id)
        except Exception:
            raise HTTPException(status_code=404, detail="task not found")
        return {"id": item_id, "status": "restored"}

    @app.delete("/api/recycle/{item_id}")
    async def delete_recycle(
        item_id: str,
        user: User = Depends(get_current_user),
        service: TaskService = Depends(get_task_service),
    ) -> Dict[str, Any]:
        RolePolicy.enforce(user.role, "task.delete")
        if item_id.startswith("trash_"):
            return {"id": item_id, "status": "deleted"}
        service.permanent_delete_task(item_id)
        return {"id": item_id, "status": "deleted"}

