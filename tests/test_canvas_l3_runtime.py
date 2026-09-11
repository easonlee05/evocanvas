"""L3 运行时主链回归测试。"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.canvas.domain.cards import CanvasCard, CanvasCardKind
from app.canvas.domain.ledger import LedgerActorType, LedgerEvent, LedgerEventType
from app.canvas.domain.mutations import (
    CanvasMutation,
    CanvasMutationAction,
    CanvasMutationProposal,
    CanvasMutationStatus,
    CanvasMutationTarget,
)
from app.canvas.domain.package import Package, PackageVersion
from app.canvas.domain.relations import CanvasRelation
from app.canvas.repository import CanvasRepository
from app.canvas.service import CanvasService
from app.services.fakes import FakeStorage

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None

from app.api.server import create_app, get_canvas_service


class CanvasL3DomainTests(unittest.TestCase):
    """验证新写入路径不再接受自由字符串状态。"""

    def test_new_card_rejects_status_not_allowed_for_its_kind(self) -> None:
        """约束卡不能以 clarification 的 open 状态创建。"""

        with self.assertRaises(ValueError):
            CanvasCard(
                card_id="card_constraint",
                kind=CanvasCardKind.CONSTRAINT,
                title="首版范围",
                status="open",
            )

    def test_compatibility_option_and_reopens_relation_are_normalized(self) -> None:
        """兼容 option/reopens 数据读取时映射到 L3 的 decision/replaces。"""

        card = CanvasCard.from_dict(
            {
                "card_id": "card_option",
                "kind": "option",
                "title": "方案 A",
                "status": "confirmed",
            }
        )
        relation = CanvasRelation.from_dict(
            {
                "relation_id": "rel_reopens",
                "kind": "reopens",
                "from_card_id": "card_a",
                "to_card_id": "card_b",
            }
        )

        self.assertEqual(card.kind.value, "decision")
        self.assertEqual(card.status, "decided")
        self.assertEqual(relation.kind.value, "replaces")


class CanvasL3RepositoryTests(unittest.TestCase):
    """验证版本提交的不可变性与账本原子可见性。"""

    def test_commit_creates_immutable_version_and_is_idempotent(self) -> None:
        """同一 operation_id 不能重复推进包指针或追加账本。"""

        with TemporaryDirectory() as tmpdir:
            repository = CanvasRepository(FakeStorage(Path(tmpdir)))
            package = Package(package_id="pkg_demo", workspace_id="demo")
            version = PackageVersion(
                package_id="pkg_demo",
                package_version=1,
                parent_version=None,
                state_version=1,
                operation_id="operation_1",
                objects=[
                    CanvasCard(
                        card_id="card_problem",
                        kind=CanvasCardKind.PROBLEM,
                        title="首版问题",
                    ).to_dict()
                ],
            )
            event = LedgerEvent(
                ledger_event_id="ledger_1",
                workspace_id="demo",
                package_id="pkg_demo",
                event_type=LedgerEventType.PACKAGE_VERSION_CREATED,
                entity_type="package_version",
                entity_id="pkg_demo:v1",
                actor_type=LedgerActorType.SYSTEM,
                actor_id="canvas_service",
                occurred_at="2026-07-14T10:00:00Z",
                package_version=1,
                operation_id="operation_1",
            )

            first = repository.commit_package_version("demo", package, version, [event])
            second = repository.commit_package_version("demo", package, version, [event])

            self.assertEqual(first.current_version, 1)
            self.assertEqual(second.current_version, 1)
            self.assertEqual(
                len(repository.query_ledger_events("demo", operation_id="operation_1")),
                1,
            )
            with self.assertRaises(FileExistsError):
                repository.save_package_version(
                    "demo",
                    PackageVersion(
                        package_id="pkg_demo",
                        package_version=1,
                        parent_version=None,
                        state_version=1,
                        objects=[],
                    ),
                )

    def test_load_detects_package_version_checksum_tampering(self) -> None:
        """磁盘版本正文被篡改时不能作为画布投影来源。"""

        with TemporaryDirectory() as tmpdir:
            repository = CanvasRepository(FakeStorage(Path(tmpdir)))
            version = PackageVersion(
                package_id="pkg_demo",
                package_version=1,
                parent_version=None,
                state_version=1,
                objects=[],
            )
            repository.save_package_version("demo", version)
            version_file = repository._package_dir("demo", "pkg_demo") / "versions" / "v1.json"
            version_file.write_text('{"package_id":"pkg_demo","package_version":1}', encoding="utf-8")

            with self.assertRaises(ValueError):
                repository.load_package_version("demo", "pkg_demo", 1)


class CanvasL3ServiceTests(unittest.TestCase):
    """验证运行时写入已经切换为包版本，而非独立 JSON 文件。"""

    def test_auto_applied_turn_commits_package_version_and_ledger(self) -> None:
        """低风险结构化整理完成后，当前画布从 package version 投影。"""

        with TemporaryDirectory() as tmpdir:
            storage = FakeStorage(Path(tmpdir))
            service = CanvasService(storage=storage)

            result = service.start_turn(
                workspace_id="demo",
                message="继续补充一期范围的待澄清问题",
                selected_card_ids=[],
                material_ids=[],
            )

            package = service.repository.load_active_package("demo")
            workspace_dir = service.repository._workspace_dir("demo")
            self.assertEqual(result["action"], "auto_apply")
            self.assertIsNotNone(package)
            self.assertEqual(package.current_version, 1)
            self.assertEqual(
                len(service.repository.query_ledger_events("demo", package_id=package.package_id)) > 0,
                True,
            )
            pending_outbox = service.repository.load_outbox("demo", status="pending")
            self.assertEqual(len(pending_outbox), 1)
            self.assertEqual(pending_outbox[0].operation_id, "operation_" + result["proposal_id"])
            self.assertFalse((workspace_dir / "cards.json").exists())
            self.assertEqual(len(service.get_canvas_view("demo")["cards"]), 1)

    def test_chat_confirmation_reuses_proposal_without_approval_queue(self) -> None:
        """高影响提议由下一条普通 Chat 确认，记录真实双向消息引用。"""

        with TemporaryDirectory() as tmpdir:
            service = CanvasService(storage=FakeStorage(Path(tmpdir)))

            service.get_workspace("demo")
            assistant_message = service.repository.append_chat_message(
                "demo",
                {
                    "message_id": "msg_assistant_proposal",
                    "role": "assistant",
                    "content": "建议把首版范围约束升级为已生效。",
                    "turn_id": "turn_proposal",
                },
            )
            proposal = CanvasMutationProposal(
                proposal_id="proposal_confirm_constraint",
                workspace_id="demo",
                turn_id="turn_proposal",
                status=CanvasMutationStatus.PENDING_CONFIRMATION,
                mutations=[
                    CanvasMutation(
                        mutation_id="mutation_confirm_constraint",
                        action=CanvasMutationAction.ADD,
                        target=CanvasMutationTarget.CARD,
                        target_id="card_effective_constraint",
                        payload={
                            "card": CanvasCard(
                                card_id="card_effective_constraint",
                                kind=CanvasCardKind.CONSTRAINT,
                                title="首版不做多人协作",
                                status="effective",
                            ).to_dict()
                        },
                        metadata={"mutation_type": "add_card"},
                    )
                ],
                metadata={
                    "awaiting_chat_confirmation": True,
                    "assistant_message_ref": assistant_message["message_id"],
                },
            )
            service.repository.append_proposal_history("demo", proposal)
            applied = service.start_turn(
                workspace_id="demo",
                message="我确认按刚才这项决策执行",
                selected_card_ids=[],
                material_ids=[],
            )

            workspace_dir = service.repository._workspace_dir("demo")
            records = service.repository.list_confirmation_records("demo")
            self.assertEqual(applied["action"], "applied_confirmation")
            self.assertEqual(len(records), 1)
            self.assertTrue(records[0].proposal_message_refs)
            self.assertTrue(records[0].user_message_refs)
            self.assertEqual(
                records[0].confirmation_path.value,
                "assistant_proposal_then_user_response",
            )
            self.assertFalse((workspace_dir / "confirmation_queue.json").exists())

    def test_confirmation_records_post_confirmation_unresolved_refs(self) -> None:
        """确认记录必须保存确认后的未决引用，而不是确认前的旧快照。"""

        with TemporaryDirectory() as tmpdir:
            service = CanvasService(storage=FakeStorage(Path(tmpdir)))
            service.get_workspace("demo")
            clarification = CanvasCard(
                card_id="card_clarification",
                kind=CanvasCardKind.CLARIFICATION,
                title="确认首版目标用户",
                status="open",
            )
            service.repository.save_cards("demo", [clarification])
            assistant_message = service.repository.append_chat_message(
                "demo",
                {
                    "message_id": "msg_assistant_resolution",
                    "role": "assistant",
                    "content": "建议确认首版目标用户为产品经理。",
                    "turn_id": "turn_resolution",
                },
            )
            proposal = CanvasMutationProposal(
                proposal_id="proposal_resolve_clarification",
                workspace_id="demo",
                turn_id="turn_resolution",
                status=CanvasMutationStatus.PENDING_CONFIRMATION,
                mutations=[
                    CanvasMutation(
                        mutation_id="mutation_resolve_clarification",
                        action=CanvasMutationAction.UPDATE,
                        target=CanvasMutationTarget.CARD,
                        target_id=clarification.card_id,
                        payload={"resolution": "首版聚焦产品经理"},
                        metadata={"mutation_type": "resolve_clarification"},
                    )
                ],
                metadata={
                    "awaiting_chat_confirmation": True,
                    "assistant_message_ref": assistant_message["message_id"],
                },
            )
            service.repository.append_proposal_history("demo", proposal)

            service.start_turn(
                workspace_id="demo",
                message="确认，按这个结论执行",
                selected_card_ids=[],
                material_ids=[],
            )

            record = service.repository.list_confirmation_records("demo")[0]
            self.assertEqual(record.remaining_unresolved_refs, [])
            self.assertEqual(service.get_canvas_view("demo")["cards"][0]["status"], "clarified")

    def test_direct_user_statement_confirmation_path(self) -> None:
        """用户直接陈述路径下 confirmation_path 为 direct_user_statement，proposal_message_refs 为空。"""

        with TemporaryDirectory() as tmpdir:
            service = CanvasService(storage=FakeStorage(Path(tmpdir)))
            service.get_workspace("demo")
            service.repository.save_cards(
                "demo",
                [
                    CanvasCard(
                        card_id="card_clarification_direct",
                        kind=CanvasCardKind.CLARIFICATION,
                        title="确认首版是否支持导出",
                        status="open",
                    )
                ],
            )
            # 构造一个没有 assistant_message_ref 的待确认提案，
            # 模拟用户直接给出清晰、完整且带范围的产品判断。
            proposal = CanvasMutationProposal(
                proposal_id="proposal_direct_statement",
                workspace_id="demo",
                turn_id="turn_direct",
                status=CanvasMutationStatus.PENDING_CONFIRMATION,
                mutations=[
                    CanvasMutation(
                        mutation_id="mutation_direct",
                        action=CanvasMutationAction.UPDATE,
                        target=CanvasMutationTarget.CARD,
                        target_id="card_clarification_direct",
                        payload={"resolution": "首版只支持 CSV 导出"},
                        metadata={"mutation_type": "resolve_clarification"},
                    )
                ],
                metadata={"awaiting_chat_confirmation": True},
            )
            service.repository.append_proposal_history("demo", proposal)

            service.start_turn(
                workspace_id="demo",
                message="确认，首版只做 CSV 导出",
                selected_card_ids=[],
                material_ids=[],
            )

            record = service.repository.list_confirmation_records("demo")[0]
            self.assertEqual(record.confirmation_path.value, "direct_user_statement")
            self.assertEqual(record.proposal_message_refs, [])
            self.assertTrue(record.user_message_refs)


class CanvasL3ApiTests(unittest.TestCase):
    """验证 API 不再暴露第二条可写状态通道。"""

    def test_card_patch_requires_chat_confirmation_for_stable_content(self) -> None:
        """稳定态卡片的标题或摘要不能绕过普通 Chat 确认被直接改写。"""

        if TestClient is None:
            self.skipTest("FastAPI not installed")
        with TemporaryDirectory() as tmpdir:
            service = CanvasService(storage=FakeStorage(Path(tmpdir)))
            service.get_workspace("demo")
            stable_constraint = CanvasCard(
                card_id="card_effective_constraint",
                kind=CanvasCardKind.CONSTRAINT,
                title="首版不做多人协作",
                summary="一期范围约束。",
                status="effective",
            )
            service.repository.save_cards("demo", [stable_constraint])

            app = create_app()
            app.dependency_overrides[get_canvas_service] = lambda: service
            client = TestClient(app)
            response = client.patch(
                "/api/canvas/workspaces/demo/cards/card_effective_constraint",
                json={"title": "首版支持多人协作"},
            )

            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["reason"], "chat_confirmation_required")
            persisted = service.repository.load_cards("demo")[0]
            self.assertEqual(persisted.title, "首版不做多人协作")

    def test_card_patch_rejects_kind_writes(self) -> None:
        """对象类型不可通过 patch 修改；待澄清卡不得改类型变成约束卡或待决策卡。"""

        with TemporaryDirectory() as tmpdir:
            service = CanvasService(storage=FakeStorage(Path(tmpdir)))
            service.get_workspace("demo")
            clarification = CanvasCard(
                card_id="card_clarify_kind",
                kind=CanvasCardKind.CLARIFICATION,
                title="确认首版目标用户",
                status="open",
            )
            service.repository.save_cards("demo", [clarification])

            with self.assertRaises(ValueError):
                service.patch_card(
                    "demo",
                    "card_clarify_kind",
                    {"kind": "constraint"},
                )
            persisted = service.repository.load_cards("demo")[0]
            self.assertEqual(persisted.kind, CanvasCardKind.CLARIFICATION)

    def test_card_patch_rejects_direct_status_writes(self) -> None:
        """状态升级只能由受控提案及普通 Chat 确认完成。"""

        if TestClient is None:
            self.skipTest("FastAPI not installed")
        client = TestClient(create_app())
        headers = {"X-Tenant-ID": "canvas-l3-api"}
        created = client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "先补充一个待澄清问题",
                "selected_card_ids": [],
                "material_ids": [],
            },
            headers=headers,
        )
        card_id = client.get(
            "/api/canvas/workspaces/demo/canvas", headers=headers
        ).json()["cards"][0]["card_id"]

        response = client.patch(
            f"/api/canvas/workspaces/demo/cards/{card_id}",
            json={"status": "clarified"},
            headers=headers,
        )

        self.assertEqual(created.status_code, 200)
        self.assertEqual(response.status_code, 422)


class CanvasL3StableCardSupersedeTests(unittest.TestCase):
    """验证稳定态卡片被替代时，过时状态必须是对应对象类型的合法类型化状态。"""

    def test_stable_decision_card_superseded_uses_archived_not_superseded(self) -> None:
        """decision 类型没有 superseded 状态；被替代时应使用 archived。"""

        with TemporaryDirectory() as tmpdir:
            from app.canvas.domain.handoff import StructuredHandoff
            from app.core.events import EventBus
            from app.services.fakes import FakeStorage

            storage = FakeStorage(Path(tmpdir), event_bus=EventBus())
            service = CanvasService(storage=storage)
            service.get_workspace("demo")

            # 写入一个已拍板的稳定决策卡（通过包版本提交）
            decided = CanvasCard(
                card_id="card_decided",
                kind=CanvasCardKind.DECISION,
                title="首版聚焦误杀成本",
                status="decided",
            )
            service.repository.save_cards("demo", [decided])
            proposal = CanvasMutationProposal(
                proposal_id="proposal_supersede",
                workspace_id="demo",
                turn_id="turn_supersede",
                status=CanvasMutationStatus.APPLIED,
                mutations=[
                    CanvasMutation(
                        mutation_id="mutation_supersede",
                        action=CanvasMutationAction.UPDATE,
                        target=CanvasMutationTarget.CARD,
                        target_id=decided.card_id,
                        payload={"title": "首版聚焦响应延迟", "summary": "修正决策方向"},
                        metadata={"mutation_type": "user_display_edit"},
                    )
                ],
                metadata={"user_edit": True},
            )
            service._apply_proposal(service.get_workspace("demo"), proposal)

            cards = service.repository.load_cards("demo")
            # 原决策卡应被替代为 archived（而非 superseded，后者对 decision 不合法）
            original = next(c for c in cards if c.card_id == "card_decided")
            self.assertEqual(original.status, "archived")
            # 治理地位应派生为 historical，而非错误降级为 working
            self.assertEqual(original.governance_class, "historical")
            # 新替代卡应存在且为 decided 状态
            new_card = next(c for c in cards if c.card_id != "card_decided" and c.kind == CanvasCardKind.DECISION)
            self.assertEqual(new_card.status, "decided")
            self.assertEqual(new_card.metadata.get("supersedes"), "card_decided")

    def test_stable_constraint_card_superseded_uses_superseded(self) -> None:
        """constraint 类型有 superseded 状态；被替代时应使用 superseded。"""

        with TemporaryDirectory() as tmpdir:
            from app.core.events import EventBus
            from app.services.fakes import FakeStorage

            storage = FakeStorage(Path(tmpdir), event_bus=EventBus())
            service = CanvasService(storage=storage)
            service.get_workspace("demo")

            effective = CanvasCard(
                card_id="card_effective",
                kind=CanvasCardKind.CONSTRAINT,
                title="一期不做多人协作",
                status="effective",
            )
            service.repository.save_cards("demo", [effective])
            proposal = CanvasMutationProposal(
                proposal_id="proposal_supersede_constraint",
                workspace_id="demo",
                turn_id="turn_supersede_constraint",
                status=CanvasMutationStatus.APPLIED,
                mutations=[
                    CanvasMutation(
                        mutation_id="mutation_supersede_constraint",
                        action=CanvasMutationAction.UPDATE,
                        target=CanvasMutationTarget.CARD,
                        target_id=effective.card_id,
                        payload={"title": "一期可探索多人协作", "summary": "修正约束方向"},
                        metadata={"mutation_type": "user_display_edit"},
                    )
                ],
                metadata={"user_edit": True},
            )
            service._apply_proposal(service.get_workspace("demo"), proposal)

            cards = service.repository.load_cards("demo")
            original = next(c for c in cards if c.card_id == "card_effective")
            # constraint 的过时态是 superseded
            self.assertEqual(original.status, "superseded")
            self.assertEqual(original.governance_class, "historical")


class CanvasL3ConfirmationPathTests(unittest.TestCase):
    """验证确认记录的 confirmation_path 字段序列化与旧数据兼容。"""

    def _build_record(self, **overrides) -> "ConfirmationRecord":
        from app.canvas.domain.confirmation import (
            ConfirmationKind,
            ConfirmationPath,
            ConfirmationRecord,
            ConfirmedClaim,
        )

        defaults = dict(
            confirmation_id="confirmation_test",
            workspace_id="demo",
            package_id="pkg_demo",
            proposal_message_refs=["msg_assistant"],
            user_message_refs=["msg_user"],
            confirmed_claims=[ConfirmedClaim(claim="首版只做 CSV")],
            scope_refs=["card_constraint_csv"],
            confirmation_kind=ConfirmationKind.CONFIRMED,
            remaining_unresolved_refs=[],
            recorded_at="2026-07-14T00:00:00Z",
            confirmation_path=ConfirmationPath.ASSISTANT_PROPOSAL_THEN_USER_RESPONSE,
        )
        defaults.update(overrides)
        return ConfirmationRecord(**defaults)

    def test_confirmation_path_serializes_to_dict(self) -> None:
        """confirmation_path 正确序列化为字符串值。"""

        record = self._build_record()
        data = record.to_dict()
        self.assertEqual(data["confirmation_path"], "assistant_proposal_then_user_response")

    def test_direct_user_statement_path_round_trips(self) -> None:
        """直接陈述路径下 proposal_message_refs 可为空，且能往返序列化。"""

        from app.canvas.domain.confirmation import ConfirmationPath, ConfirmationRecord

        record = self._build_record(
            confirmation_path=ConfirmationPath.DIRECT_USER_STATEMENT,
            proposal_message_refs=[],
        )
        restored = ConfirmationRecord.from_dict(record.to_dict())
        self.assertEqual(restored.confirmation_path, ConfirmationPath.DIRECT_USER_STATEMENT)
        self.assertEqual(restored.proposal_message_refs, [])

    def test_compatibility_record_without_confirmation_path_defaults_to_assistant_proposal(self) -> None:
        """兼容持久化数据缺失 confirmation_path 时按 assistant 提议路径恢复。"""

        from app.canvas.domain.confirmation import ConfirmationPath, ConfirmationRecord

        compatibility_data = {
            "confirmation_id": "confirmation_compatibility",
            "workspace_id": "demo",
            "package_id": "pkg_demo",
            "proposal_message_refs": ["msg_assistant"],
            "user_message_refs": ["msg_user"],
            "confirmed_claims": [{"claim": "旧确认"}],
            "scope_refs": [],
            "confirmation_kind": "confirmed",
            "remaining_unresolved_refs": [],
            "recorded_at": "2026-01-01T00:00:00Z",
        }
        restored = ConfirmationRecord.from_dict(compatibility_data)
        self.assertEqual(
            restored.confirmation_path,
            ConfirmationPath.ASSISTANT_PROPOSAL_THEN_USER_RESPONSE,
        )


if __name__ == "__main__":
    unittest.main()
