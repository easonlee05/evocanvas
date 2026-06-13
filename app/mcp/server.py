"""Evoloop 3.0 MCP (Model Context Protocol) 协议服务入口。

该模块实例化了一个 FastMCP 服务实例，注册全部 Tools（工具能力）和 Resources（受控资源），
并通过标准的 StdIO (标准输入输出) 管道暴露服务，与上层智能体运行环境（如 Cursor, Claude Code, Cline 等）进行通信。
"""
import sys

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    # 如果运行环境下未安装 mcp 协议包，则提前进行错误警示并退出
    print("mcp package is not installed. Please install mcp to run this server.", file=sys.stderr)
    sys.exit(1)

from app.mcp.tools import register_tools
from app.mcp.resources import register_resources

# 实例化 FastMCP 控制面服务，命名为 Evoloop 3.0 PM 控制面
mcp = FastMCP("Evoloop_3.0_PM_Control_Plane")

# 统一注册所有的工具与资源
register_tools(mcp)
register_resources(mcp)


def main():
    """启动基于标准输入输出 (StdIO) 传输协议的 MCP 服务器。"""
    mcp.run()


if __name__ == "__main__":
    main()
