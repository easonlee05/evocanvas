#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "======================================================"
echo "      EvoCanvas 免费公网一键分享 (Cloudflare Tunnel)  "
echo "======================================================"

# 1. 检查 cloudflared 工具
if ! command -v cloudflared &>/dev/null; then
  echo "正在安装免费穿透工具 cloudflared..."
  brew install cloudflared
fi

# 2. 读取本地 .env 配置
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

if [ -z "$DEEPSEEK_API_KEY" ]; then
  echo "------------------------------------------------------"
  echo "【提示】未检测到 DEEPSEEK_API_KEY 环境变量。"
  echo "如果你有 DeepSeek API Key，可以在项目根目录创建 .env 文件写入："
  echo "DEEPSEEK_API_KEY=sk-你的真实Key"
  echo "------------------------------------------------------"
fi

# 3. 确保前端和运行时已完成构建
if [ ! -f "frontend/dist/index.html" ]; then
  echo "正在构建前端生产静态包..."
  npm --prefix frontend run build
fi

if [ ! -f "pi-runtime/dist/server.js" ]; then
  echo "正在构建 Pi Runtime 运行时..."
  npm --prefix pi-runtime run build
fi

# 4. 配置运行环境
export PI_RUNTIME_HOST="127.0.0.1"
export PI_RUNTIME_PORT="8790"
export PI_RUNTIME_URL="http://127.0.0.1:8790"
export EVO_STORAGE_DIR="$DIR/workspace-data"
export PI_STORAGE_DIR="$DIR/.pi-storage"

mkdir -p "$EVO_STORAGE_DIR" "$PI_STORAGE_DIR"

# 5. 后台启动 Pi Runtime
echo "1. 启动 Pi Runtime 服务..."
node pi-runtime/dist/server.js &
PI_PID=$!

# 6. 后台启动 FastAPI 服务
PYTHON_BIN="python3"
if [ -f ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
fi

echo "2. 启动 FastAPI Web 服务..."
"$PYTHON_BIN" -m uvicorn app.api.server:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

cleanup() {
  echo ""
  echo "正在停止所有服务与公网隧道..."
  kill -TERM "$CLOUDFLARE_PID" 2>/dev/null || true
  kill -TERM "$BACKEND_PID" 2>/dev/null || true
  kill -TERM "$PI_PID" 2>/dev/null || true
  wait "$BACKEND_PID" 2>/dev/null || true
  wait "$PI_PID" 2>/dev/null || true
  echo "服务已全部安全退出。"
  exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 7. 等待本地服务就绪
echo "3. 等待服务就绪并健康检查..."
until curl -s http://127.0.0.1:8000/api/health >/dev/null; do
  sleep 0.5
done
echo "本地服务健康检查通过！"

# 8. 启动 Cloudflare 免费公网隧道
echo "4. 正在建立免费全球公网 HTTPS 隧道..."
cloudflared tunnel --url http://127.0.0.1:8000 2>&1 | tee /tmp/cloudflared_evocanvas.log &
CLOUDFLARE_PID=$!

# 从日志中提取分配的公网 URL
echo "正在获取公网访问网址..."
TUNNEL_URL=""
for i in {1..30}; do
  if grep -q "trycloudflare.com" /tmp/cloudflared_evocanvas.log 2>/dev/null; then
    TUNNEL_URL=$(grep -o 'https://[-a-zA-Z0-9@:%._\+~#=]*\.trycloudflare\.com' /tmp/cloudflared_evocanvas.log | head -n 1)
    if [ -n "$TUNNEL_URL" ]; then
      break
    fi
  fi
  sleep 1
done

if [ -n "$TUNNEL_URL" ]; then
  echo "======================================================"
  echo "🎉 恭喜！你的 EvoCanvas 网站已成功发布到公网！"
  echo ""
  echo "👉 公网访问网址: ${TUNNEL_URL}"
  echo ""
  echo "任何人在手机、电脑浏览器打开上方网址，即可上手即用！"
  echo "（按 Ctrl+C 可随时停止对外服务）"
  echo "======================================================"
else
  echo "[提示] 隧道已启动，请查看上方日志中的 trycloudflare.com 链接"
fi

wait "$CLOUDFLARE_PID"
