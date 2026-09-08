#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "======================================================"
echo "          EvoCanvas 在线网站服务一键启动 (裸机模式)      "
echo "======================================================"

# 1. 尝试加载 .env 配置文件
if [ -f .env ]; then
  echo "正在读取 .env 环境变量..."
  set -a
  source .env
  set +a
fi

# 2. 检查必须的 LLM 凭证
if [ -z "$DEEPSEEK_API_KEY" ]; then
  echo "[警告] 未检测到 DEEPSEEK_API_KEY 环境变量！"
  echo "       请先在 .env 中填入大模型凭证，否则 AI 收敛回路将无法正常响应。"
fi

# 3. 检查并按需构建前端产物
if [ ! -f "frontend/dist/index.html" ]; then
  echo "未检测到前端构建产物，正在执行前端构建 (npm run build)..."
  npm --prefix frontend install
  npm --prefix frontend run build
fi

# 4. 检查并按需构建 Pi Runtime 产物
if [ ! -f "pi-runtime/dist/server.js" ]; then
  echo "未检测到 Pi Runtime 构建产物，正在执行构建..."
  npm --prefix pi-runtime install
  npm --prefix pi-runtime run build
fi

# 5. 配置内部通信端口与持久化路径
export PI_RUNTIME_HOST="${PI_RUNTIME_HOST:-127.0.0.1}"
export PI_RUNTIME_PORT="${PI_RUNTIME_PORT:-8790}"
export PI_RUNTIME_URL="http://${PI_RUNTIME_HOST}:${PI_RUNTIME_PORT}"
export EVO_STORAGE_DIR="${EVO_STORAGE_DIR:-$DIR/workspace-data}"
export PI_STORAGE_DIR="${PI_STORAGE_DIR:-$DIR/.pi-storage}"

mkdir -p "$EVO_STORAGE_DIR" "$PI_STORAGE_DIR"

# 6. 后台拉起 Pi Runtime
echo "正在启动 Pi Runtime 进程 (${PI_RUNTIME_URL})..."
node pi-runtime/dist/server.js &
PI_PID=$!

# 7. 优雅停止处理
cleanup() {
  echo ""
  echo "接收到停止信号，正在退出所有 EvoCanvas 进程..."
  kill -TERM "$BACKEND_PID" 2>/dev/null || true
  kill -TERM "$PI_PID" 2>/dev/null || true
  wait "$BACKEND_PID" 2>/dev/null || true
  wait "$PI_PID" 2>/dev/null || true
  echo "服务已停止。"
  exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 等待 Pi Runtime 端口就绪
sleep 1

# 8. 选择 Python 解释器
PYTHON_BIN="python3"
if [ -f ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
fi

PORT="${PORT:-8000}"
echo "正在启动 FastAPI Web 生产服务 (http://0.0.0.0:${PORT})..."
echo "======================================================"
echo "  EvoCanvas 网站已成功运行！"
echo "  本机访问地址: http://localhost:${PORT}"
echo "  云服务器公网: http://<你的服务器IP>:${PORT}"
echo "======================================================"

"$PYTHON_BIN" -m uvicorn app.api.server:app --host 0.0.0.0 --port "$PORT" &
BACKEND_PID=$!

wait "$BACKEND_PID"
