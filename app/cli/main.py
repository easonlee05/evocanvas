"""Evoloop 3.0 CLI 命令行工具入口模块。

本模块利用 Python argparse 标准库解析命令行参数，
并将各个子命令（compile, package, acceptance, review）的操作请求分发传递给 commands 模块进行底层执行。
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from app.cli.commands import compile_cmd, package_cmd, acceptance_cmd, review_cmd


def main(args: Optional[List[str]] = None) -> None:
    """解析 CLI 命令行参数并执行对应的业务指令。

    Args:
        args (Optional[List[str]]): 命令行参数列表，默认由 sys.argv 传入。
    """
    parser = argparse.ArgumentParser(
        description="Evoloop 3.0 CLI 适配器 - 终端级数字 PM 能力控制台"
    )
    subparsers = parser.add_subparsers(dest="command", help="支持的二级子命令集")

    # 1. 注册 compile (编译) 命令参数解析器
    compile_parser = subparsers.add_parser("compile", help="编译业务意图为可被 AI 理解的系统需求规格")
    compile_parser.add_argument(
        "-i", "--intent", 
        type=str, 
        required=True, 
        help="用户输入的业务诉求或核心产品意图描述"
    )
    compile_parser.add_argument(
        "-m", "--materials", 
        type=str, 
        nargs="*", 
        default=[], 
        help="待参考的补充文档、遗留代码或业务规章等背景上下文文件路径"
    )
    compile_parser.add_argument(
        "--output-dir", 
        type=str, 
        default=".", 
        help="编译输出 machine_spec.yaml 与 human_brief.md 的目标文件夹路径"
    )
    compile_parser.add_argument(
        "--fake", 
        action="store_true", 
        help="启用 Mock 伪大模型及本地虚拟存储跑工作流（离线无网试跑）"
    )

    # 2. 注册 package (打包) 命令参数解析器
    package_parser = subparsers.add_parser("package", help="根据编译规约文件生成用于分发给研发智能体的分包")
    package_parser.add_argument(
        "-s", "--spec", 
        type=str, 
        default="./machine_spec.yaml", 
        help="输入 machine_spec.yaml 规格说明书路径"
    )
    package_parser.add_argument(
        "-o", "--output", 
        type=str, 
        default="./agent_package.md", 
        help="打包任务描述输出文件的路径"
    )
    package_parser.add_argument(
        "--fake", 
        action="store_true", 
        help="启用 Mock 模式生成伪任务包文件"
    )

    # 3. 注册 acceptance (验收协议生成) 命令参数解析器
    acceptance_parser = subparsers.add_parser("acceptance", help="根据编译规约文件生成覆盖各需求的验收测试指标")
    acceptance_parser.add_argument(
        "-s", "--spec", 
        type=str, 
        default="./machine_spec.yaml", 
        help="输入 machine_spec.yaml 规格说明书路径"
    )
    acceptance_parser.add_argument(
        "-o", "--output", 
        type=str, 
        default="./acceptance.md", 
        help="验收指标协议说明书输出文件路径"
    )
    acceptance_parser.add_argument(
        "--fake", 
        action="store_true", 
        help="启用 Mock 模式生成伪验收指标文件"
    )

    # 4. 注册 review (交付物审查) 命令参数解析器
    review_parser = subparsers.add_parser("review", help="结合验收协议，对 AI 研发交付的最终代码或产物进行一致性与准入审计")
    review_parser.add_argument(
        "-s", "--spec", 
        type=str, 
        default="./machine_spec.yaml", 
        help="输入 machine_spec.yaml 规格说明书路径"
    )
    review_parser.add_argument(
        "-a", "--acceptance", 
        type=str, 
        default="./acceptance.md", 
        help="输入 acceptance.md 验收指标协议说明书路径"
    )
    review_parser.add_argument(
        "-d", "--delivery", 
        type=str, 
        required=True, 
        help="研发智能体交付的待评估源码字符串、纯文本内容或保存路径"
    )
    review_parser.add_argument(
        "-o", "--output", 
        type=str, 
        default="./review_result.md", 
        help="审计结论报告输出文件 review_result.md 路径"
    )
    review_parser.add_argument(
        "--fake", 
        action="store_true", 
        help="启用 Mock 模式执行伪准入审计"
    )

    # 解析当前输入命令行参数并分发派发
    parsed_args = parser.parse_args(args)

    if parsed_args.command == "compile":
        compile_cmd(
            intent=parsed_args.intent,
            materials=parsed_args.materials,
            output_dir=parsed_args.output_dir,
            fake=parsed_args.fake
        )
    elif parsed_args.command == "package":
        package_cmd(
            spec_path=parsed_args.spec,
            output_path=parsed_args.output,
            fake=parsed_args.fake
        )
    elif parsed_args.command == "acceptance":
        acceptance_cmd(
            spec_path=parsed_args.spec,
            output_path=parsed_args.output,
            fake=parsed_args.fake
        )
    elif parsed_args.command == "review":
        review_cmd(
            spec_path=parsed_args.spec,
            acceptance_path=parsed_args.acceptance,
            delivery_text_or_path=parsed_args.delivery,
            output_path=parsed_args.output,
            fake=parsed_args.fake
        )
    else:
        # 如果未匹配到子命令，则默认输出 CLI 帮助文档提示
        parser.print_help()


if __name__ == "__main__":
    main()
