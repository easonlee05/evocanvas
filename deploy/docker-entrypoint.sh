#!/bin/sh
set -e

# 设置存储与网络默认值
export PI_STORAGE_DIR="${PI_STORAGE_DIR:-/data/pi-storage}"
export EVO_STORAGE_DIR="${EVO_STORAGE_DIR:-/data/evocanvas-storage}"
export PI_RUNTIME_HOST="127.0.0.1"
export PI_RUNTIME_PORT="${PI_RUNTIME_PORT:-8790}"
export PI_RUNTIME_URL="http://127.0.0.1:${PI_RUNTIME_PORT}"
export FRONTEND_DIST_DIR="${FRONTEND_DIST_DIR:-/app/frontend/dist}"

mkdir -p "$PI_STORAGE_DIR" "$EVO_STORAGE_DIR"

echo "======================================================"
echo "          Starting EvoCanvas Production System        "
echo "======================================================"

# 启动 Pi Runtime 后台服务
echo "1. 正在启动 Pi Runtime 运行时 (端口 ${PI_RUNTIME_PORT})..."
node /app/pi-runtime/dist/server.js &
PI_PID=$!

# 退出信号捕捉
cleanup() {
    echo "正在停止容器内所有进程..."
    kill -TERM "$BACKEND_PID" 2>/dev/null || true
    kill -TERM "$PI_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
    wait "$PI_PID" 2>/dev/null || true
    exit 0
}
# POSIX /bin/sh 兼容写法；部分 slim 镜像不接受带 SIG 前缀的信号名。
trap cleanup INT TERM

# 等待 Pi Runtime 监听启动
sleep 1

# 启动 FastAPI 后端服务
PORT="${PORT:-8000}"
echo "2. 正在启动 FastAPI Web 生产服务 (端口 ${PORT})..."
uvicorn app.api.server:app --host 0.0.0.0 --port "$PORT" &
BACKEND_PID=$!

echo "EvoCanvas 已成功运行！"
wait "$BACKEND_PID"
