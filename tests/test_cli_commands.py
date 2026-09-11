"""
EvoCanvas CLI 命令行工具及工具函数集成测试模块。

本测试文件主要验证 EvoCanvas 命令行实用程序及辅助函数的正确性，主要覆盖以下模块：
1. `TestCLIUtils`: 针对命令行输出长文本折叠逻辑（compact_error_text）以及 YAML 文件安全读写（read_yaml_safe / write_yaml_safe）的单元测试。
2. `TestCLICommands`: 针对产物依赖图（ArtifactGraph）校验规则，以及核心 CLI 子命令：
   - compile_cmd: 编译业务意图为机器规格（machine_spec.yaml）与人机 brief（human_brief.md）。
   - package_cmd: 从机器规格打包生成 agent 执行包（agent_package.md）。
   - acceptance_cmd: 生成验收协议（acceptance.md）。
   - review_cmd: 执行验收评审，输出评审报告（review_result.md）。
3. `TestCLIMain`: 通过 Mock 拦截测试命令行接口（app.cli.main）的参数解析与子命令正确分发。
"""

import unittest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import patch

try:
    import yaml
except ImportError:
    yaml = None

from app.cli.utils import compact_error_text, read_yaml_safe, write_yaml_safe
from app.cli.commands import compile_cmd, package_cmd, acceptance_cmd, review_cmd
from app.core.artifact_graph import (
    ArtifactGraph, ArtifactNode, ArtifactEdge, ArtifactNodeType,
    ArtifactEdgeType, ArtifactRef, ArtifactGraphValidationError
)


class TestCLIUtils(unittest.TestCase):
    """
    命令行辅助工具函数的单元测试类。

    主要验证长文本输出的缩略截断机制以及 YAML 格式数据的读写可靠性。
    """

    def test_compact_error_text_no_folding(self):
        """
        验证当错误日志行数小于设定的最大行数时，不发生任何文本折叠。

        业务输入：
        - 长度为 10 行的文本，限制最大行数为 15。

        断言：
        - 返回文本与原始文本完全一致。
        """
        text = "\n".join(f"line {i}" for i in range(10))
        result = compact_error_text(text, max_lines=15)
        self.assertEqual(result, text)

    def test_compact_error_text_with_folding(self):
        """
        验证当错误日志行数超出最大限制时，折叠多余行并插入缩略占位提示。

        业务输入：
        - 长度为 50 行的文本，限制最大行数为 15。

        断言：
        - 检查返回日志中包含折叠说明提示。
        - 保证首行与末行文本依然保留以保持日志上下文。
        """
        text = "\n".join(f"line {i}" for i in range(50))
        result = compact_error_text(text, max_lines=15)
        # 注意：此处断言在本地化翻译时可能会有 failure 差异，但根据不改变测试逻辑的黄金规则，本断言保持不变
        self.assertIn("折叠了 36 行输出", result)
        self.assertTrue(result.startswith("line 0"))
        self.assertTrue(result.endswith("line 49"))

    def test_yaml_safe_operations(self):
        """
        测试 YAML 格式文件的安全序列化与反序列化操作。

        测试点：
        - 正常写入嵌套 Dict 结构的数据并确认返回成功、文件存在。
        - 正常读取刚才写入的 YAML 并验证内容等价性。
        - 读取不存在的文件时安全返回 None 而非抛出 IO 异常。
        """
        temp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(temp_dir))
        
        yaml_path = Path(temp_dir) / "test.yaml"
        data = {"key": "value", "nested": {"num": 42}}
        
        # 1. 写入验证
        write_success = write_yaml_safe(str(yaml_path), data)
        self.assertTrue(write_success)
        self.assertTrue(yaml_path.exists())
        
        # 2. 读取验证
        read_data = read_yaml_safe(str(yaml_path))
        self.assertEqual(read_data, data)
        
        # 3. 缺失文件验证
        self.assertIsNone(read_yaml_safe(str(Path(temp_dir) / "missing.yaml")))


class TestCLICommands(unittest.TestCase):
    """
    EvoCanvas 核心 CLI 命令行命令的单元测试类。

    使用临时目录作为执行沙盒，模拟文件读写并校验生成的 Markdown 报表。
    """

    def setUp(self):
        """
        初始化测试脚手架，创建隔离的临时输入输出目录。
        """
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = Path(self.temp_dir) / "output"
        self.output_dir.mkdir()

    def tearDown(self):
        """
        清理临时测试沙盒目录。
        """
        shutil.rmtree(self.temp_dir)

    def _write_mock_spec(self, path: Path, data: dict):
        """
        写入模拟机器规格文件的辅助方法。根据系统环境选择 yaml 或 json。
        """
        if yaml is not None:
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f)
        else:
            import json
            path.write_text(json.dumps(data), encoding="utf-8")

    def test_artifact_graph_validation_rules(self):
        """
        验证产物图（ArtifactGraph）的拓扑关系及节点存在性校验逻辑。

        校验规则断言：
        - 仅包含 HUMAN_BRIEF，缺少 MACHINE_SPEC 节点 -> 抛出验证错误。
        - 同时包含 MACHINE_SPEC 与 HUMAN_BRIEF，但是拓扑关系中没有任何依赖边 -> 抛出验证错误。
        - 包含错误的依赖边（自 MACHINE_SPEC 指向 HUMAN_BRIEF 属于倒置关系） -> 抛出验证错误。
        - 正确的依赖边方向（HUMAN_BRIEF 作为输入通过 DERIVES_FROM 衍生出 MACHINE_SPEC） -> 校验正常通过。
        """
        # 1. 缺少必要节点
        graph = ArtifactGraph(
            work_id="test_work",
            nodes=[
                ArtifactNode(
                    node_id="brief",
                    type=ArtifactNodeType.HUMAN_BRIEF,
                    artifact_ref=ArtifactRef(name="human_brief")
                )
            ],
            edges=[]
        )
        with self.assertRaises(ArtifactGraphValidationError):
            graph.validate()

        # 2. 节点孤立无边
        graph = ArtifactGraph(
            work_id="test_work",
            nodes=[
                ArtifactNode(
                    node_id="spec",
                    type=ArtifactNodeType.MACHINE_SPEC,
                    artifact_ref=ArtifactRef(name="machine_spec")
                ),
                ArtifactNode(
                    node_id="brief",
                    type=ArtifactNodeType.HUMAN_BRIEF,
                    artifact_ref=ArtifactRef(name="human_brief")
                )
            ],
            edges=[]
        )
        with self.assertRaises(ArtifactGraphValidationError):
            graph.validate()

        # 3. 边依赖方向反向
        graph = ArtifactGraph(
            work_id="test_work",
            nodes=[
                ArtifactNode(
                    node_id="spec",
                    type=ArtifactNodeType.MACHINE_SPEC,
                    artifact_ref=ArtifactRef(name="machine_spec")
                ),
                ArtifactNode(
                    node_id="brief",
                    type=ArtifactNodeType.HUMAN_BRIEF,
                    artifact_ref=ArtifactRef(name="human_brief")
                )
            ],
            edges=[
                ArtifactEdge(
                    edge_id="edge_rev",
                    from_node_id="spec",
                    to_node_id="brief",
                    type=ArtifactEdgeType.DERIVES_FROM
                )
            ]
        )
        with self.assertRaises(ArtifactGraphValidationError):
            graph.validate()

        # 4. 正确的产物依赖拓扑
        graph = ArtifactGraph(
            work_id="test_work",
            nodes=[
                ArtifactNode(
                    node_id="spec",
                    type=ArtifactNodeType.MACHINE_SPEC,
                    artifact_ref=ArtifactRef(name="machine_spec")
                ),
                ArtifactNode(
                    node_id="brief",
                    type=ArtifactNodeType.HUMAN_BRIEF,
                    artifact_ref=ArtifactRef(name="human_brief")
                )
            ],
            edges=[
                ArtifactEdge(
                    edge_id="edge_ok",
                    from_node_id="brief",
                    to_node_id="spec",
                    type=ArtifactEdgeType.DERIVES_FROM
                )
            ]
        )
        graph.validate()

    @patch('builtins.input', side_effect=["1", "自定义裁决方案"])
    def test_compile_command_interactive(self, mock_input):
        """
        测试 compile 命令在交互模式下的编译效果。

        模拟：
        - Mock 用户的 stdin 输入，选择特定编号并输入自定义方案。

        断言：
        - 产物 machine_spec.yaml 与 human_brief.md 被成功创建于 output 目录。
        - 两份文件中均成功检索到了编译后的业务主旨信息。
        """
        intent = "设计一个带缓存的商品详情接口"
        materials = []
        compile_cmd(
            intent=intent,
            materials=materials,
            output_dir=str(self.output_dir),
            fake=True
        )
        
        spec_file = self.output_dir / "machine_spec.yaml"
        brief_file = self.output_dir / "human_brief.md"
        
        self.assertTrue(spec_file.exists(), "machine_spec.yaml should be created")
        self.assertTrue(brief_file.exists(), "human_brief.md should be created")
        
        spec_content = spec_file.read_text(encoding="utf-8")
        self.assertIn("商品详情接口", spec_content)
        
        brief_content = brief_file.read_text(encoding="utf-8")
        self.assertIn("商品详情接口", brief_content)

    def test_package_command(self):
        """
        测试 package 打包命令。

        验证系统能读取机器规格，并将其打包转译为面向下游 AI Worker 执行的 markdown 格式的 Agent Package。
        """
        spec_file = self.output_dir / "machine_spec.yaml"
        spec_data = {
            "title": "缓存设计",
            "objective": "验证CLI打包生成",
            "requirements": [{"requirement_id": "r1", "statement": "支持 Redis"}]
        }
        self._write_mock_spec(spec_file, spec_data)
            
        package_file = self.output_dir / "agent_package.md"
        
        package_cmd(
            spec_path=str(spec_file),
            output_path=str(package_file),
            fake=True
        )
        
        self.assertTrue(package_file.exists())
        content = package_file.read_text(encoding="utf-8")
        self.assertIn("缓存设计", content)
        self.assertIn("验证CLI打包生成", content)

    def test_acceptance_command(self):
        """
        测试 acceptance 验收协议生成命令。

        验证系统能够基于 machine_spec 中规范的需求点，自动派生包含对应测试用例架构的验收协议。
        """
        spec_file = self.output_dir / "machine_spec.yaml"
        spec_data = {
            "title": "鉴权网关",
            "objective": "保护内部微服务",
            "requirements": [{"requirement_id": "r2", "statement": "拦截未授权请求"}]
        }
        self._write_mock_spec(spec_file, spec_data)
            
        acceptance_file = self.output_dir / "acceptance.md"
        
        acceptance_cmd(
            spec_path=str(spec_file),
            output_path=str(acceptance_file),
            fake=True
        )
        
        self.assertTrue(acceptance_file.exists())
        content = acceptance_file.read_text(encoding="utf-8")
        self.assertIn("鉴权网关", content)
        self.assertIn("拦截未授权请求", content)

    def test_review_command(self):
        """
        测试 review 验收评审命令。

        基于输入的 machine_spec、验收协议以及具体的开发代码交付物（delivery），
        启动 Reviewer 编译判定，生成 Verdict 报告。
        """
        spec_file = self.output_dir / "machine_spec.yaml"
        spec_data = {
            "title": "鉴权网关",
            "objective": "保护内部微服务",
            "requirements": [{"requirement_id": "r2", "statement": "拦截未授权请求"}]
        }
        self._write_mock_spec(spec_file, spec_data)
            
        acc_file = self.output_dir / "acceptance.md"
        acc_file.write_text("# 验收协议\n- 拦截未授权请求需返回 401\n", encoding="utf-8")
        
        review_file = self.output_dir / "review_result.md"
        
        review_cmd(
            spec_path=str(spec_file),
            acceptance_path=str(acc_file),
            delivery_text_or_path="开发已实现拦截逻辑，未携带 token 返回 401。",
            output_path=str(review_file),
            fake=True
        )
        
        self.assertTrue(review_file.exists())
        content = review_file.read_text(encoding="utf-8")
        self.assertIn("Review Verdict", content)
        self.assertIn("r2", content)

    def test_review_command_non_fake_does_not_unconditionally_pass_todo_delivery(self):
        """非 fake 模式必须走真实验收评审链路，不能固定输出 PASS。"""
        spec_file = self.output_dir / "machine_spec.yaml"
        spec_data = {
            "title": "鉴权网关",
            "objective": "保护内部微服务",
            "requirements": [{"requirement_id": "r2", "statement": "拦截未授权请求"}],
        }
        self._write_mock_spec(spec_file, spec_data)

        acc_file = self.output_dir / "acceptance.md"
        acc_file.write_text("# 验收协议\n- 拦截未授权请求需返回 401\n", encoding="utf-8")

        review_file = self.output_dir / "review_result.md"

        review_cmd(
            spec_path=str(spec_file),
            acceptance_path=str(acc_file),
            delivery_text_or_path="+ // TODO: 鉴权失败分支尚未实现",
            output_path=str(review_file),
            fake=False,
        )

        content = review_file.read_text(encoding="utf-8")
        self.assertIn("Verdict: blocked", content)
        self.assertIn("存在未完成的 TODO 开发项", content)
        self.assertNotIn("Review Verdict: PASS", content)


class TestCLIMain(unittest.TestCase):
    """
    CLI 统一入口点（main）及参数分发单元测试类。

    利用 Mock patch 保证实际不启动复杂大模型，只拦截参数列表并断言各字段的对齐关系。
    """

    @patch('app.cli.main.compile_cmd')
    def test_main_compile_args(self, mock_compile):
        """
        验证 compile 子命令的传参和参数绑定行为。
        """
        from app.cli.main import main
        main(["compile", "--intent", "test_intent", "-m", "mat1", "mat2", "--output-dir", "/tmp/out"])
        mock_compile.assert_called_once_with(
            intent="test_intent",
            materials=["mat1", "mat2"],
            output_dir="/tmp/out",
            fake=False
        )

    @patch('app.cli.main.package_cmd')
    def test_main_package_args(self, mock_package):
        """
        验证 package 子命令的传参和参数绑定行为。
        """
        from app.cli.main import main
        main(["package", "--spec", "spec.yaml", "--output", "pkg.md", "--fake"])
        mock_package.assert_called_once_with(
            spec_path="spec.yaml",
            output_path="pkg.md",
            fake=True
        )

    @patch('app.cli.main.acceptance_cmd')
    def test_main_acceptance_args(self, mock_acceptance):
        """
        验证 acceptance 子命令的传参和参数绑定行为。
        """
        from app.cli.main import main
        main(["acceptance", "--spec", "spec.yaml", "--output", "acc.md", "--fake"])
        mock_acceptance.assert_called_once_with(
            spec_path="spec.yaml",
            output_path="acc.md",
            fake=True
        )

    @patch('app.cli.main.review_cmd')
    def test_main_review_args(self, mock_review):
        """
        验证 review 子命令的传参和参数绑定行为。
        """
        from app.cli.main import main
        main(["review", "--spec", "spec.yaml", "--acceptance", "acc.md", "--delivery", "del.txt", "--output", "rev.md", "--fake"])
        mock_review.assert_called_once_with(
            spec_path="spec.yaml",
            acceptance_path="acc.md",
            delivery_text_or_path="del.txt",
            output_path="rev.md",
            fake=True
        )


if __name__ == "__main__":
    unittest.main()
