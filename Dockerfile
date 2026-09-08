# ==============================================================================
# EvoCanvas 生产多阶段构建 Dockerfile
# 支持一站式打包 Frontend, Pi Runtime (Node 22) 与 FastAPI 后端 (Python 3.12)
# ==============================================================================

# ----------------- 阶段 1: 前端生产构建 -----------------
FROM node:22-bookworm-slim AS frontend-builder
WORKDIR /build/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ----------------- 阶段 2: Pi Runtime 生产构建 -----------------
FROM node:22-bookworm-slim AS runtime-builder
WORKDIR /build/pi-runtime

COPY pi-runtime/package*.json ./
RUN npm ci

COPY pi-runtime/ ./
RUN npm run build
# 移除非生产依赖，减小镜像体积
RUN npm prune --production

# ----------------- 阶段 3: 最终运行镜像 -----------------
FROM python:3.12-slim-bookworm AS runner

# 复制 Node 22 运行二进制与必要库文件
COPY --from=node:22-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules

# 安装系统级基础工具（curl 用于健康检查）
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY app/requirements.txt /app/app/requirements.txt
RUN pip install --no-cache-dir -r /app/app/requirements.txt

# 拷贝后端核心代码
COPY app /app/app

# 拷贝 Pi Runtime 产物与生产 node_modules
COPY --from=runtime-builder /build/pi-runtime /app/pi-runtime

# 拷贝前端构建产物
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

# 拷贝容器启动脚本并赋权
COPY deploy/docker-entrypoint.sh /app/deploy/docker-entrypoint.sh
RUN chmod +x /app/deploy/docker-entrypoint.sh

# 环境变量配置
ENV PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    FRONTEND_DIST_DIR=/app/frontend/dist \
    PORT=8000

# 创建持久化数据卷挂载点
RUN mkdir -p /data/pi-storage /data/evocanvas-storage
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://127.0.0.1:8000/api/health || exit 1

ENTRYPOINT ["/app/deploy/docker-entrypoint.sh"]
