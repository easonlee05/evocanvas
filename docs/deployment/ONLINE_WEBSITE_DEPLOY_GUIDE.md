# EvoCanvas 在线网站部署与上线指南

本指南指导你将 **EvoCanvas** 作为公共或团队内部的**在线 Web 网站**部署到云服务器，实现最终用户**“零安装、开箱即用”**（只需浏览器打开网址即可体验完整的需求感觉塑形与画布收敛功能）。

---

## 1. 架构总览

在上线部署形态下，整个系统的调用拓扑如下：

```
[最终用户浏览器]
       │
       ▼ (80 / 443 端口, HTTP/HTTPS)
[Nginx 反向代理] (可选，负责域名、SSL 证书与静态缓存)
       │
       ▼ (8000 端口)
[FastAPI Web 服务]
  ├── 统一托管前端 SPA 静态页面 (/)
  ├── 业务 API 路由 (/api/...)
  └── 连接 AI 运行时 (http://127.0.0.1:8790)
       │
       ▼ (8790 端口)
[Pi Runtime 运行时] (Node.js 22)
  ├── 驱动 Primary Pi Session
  ├── 维护 SQLite 事务 Revision 数据库
  └── 调用 DeepSeek / OpenAI 大模型 API
```

---

## 2. 云服务器准备建议

- **云厂商**：阿里云、腾讯云、华为云、AWS、轻量应用服务器或海外 VPS 均可。
- **推荐配置**：
  - **CPU / 内存**：2 核 4G 内存及以上（构建阶段 npm/tsc 较占内存；若在本地构建好镜像推送到服务器，1 核 2G 亦可平稳运行）。
  - **操作系统**：Ubuntu 22.04 LTS / 24.04 LTS 或 Debian 12。
  - **网络带宽**：3Mbps ~ 5Mbps 以上（便于快速加载前端资源）。
  - **防火墙 / 安全组**：需放行 `80`（HTTP）、`443`（HTTPS），如直接通过端口访问需放行 `8000`。

---

## 3. 推荐部署方式：Docker Compose 一键上线（最省心）

由于项目中的 AI 核心运行时 `pi-runtime` 严格依赖 **Node.js >= 22.19.0**，直接在宿主机配置多版本环境容易遇到系统兼容问题。使用 Docker 能够彻底抹平环境差异。

### 步骤 1：在服务器安装 Docker 与 Docker Compose
如果服务器尚未安装 Docker：
```bash
# Ubuntu / Debian 官方安装脚本
curl -fsSL https://get.docker.com | bash -s docker
systemctl enable --now docker
```

### 步骤 2：上传代码或拉取仓库
将项目代码上传至服务器（例如 `/opt/evocanvas`）：
```bash
git clone <your-repo-url> /opt/evocanvas
cd /opt/evocanvas
```

### 步骤 3：配置环境变量
复制配置模板并填入你的大模型 API Key：
```bash
cp .env.example .env
nano .env   # 或 vim .env
```
确保配置了有效的凭证：
```ini
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
PORT=8000
```

### 步骤 4：一键构建并启动
在项目根目录下执行：
```bash
docker compose up -d --build
```
此时 Docker 会自动完成前端构建、Runtime 编译及 FastAPI 容器打包。

### 步骤 5：检查运行状态
```bash
# 查看容器日志
docker compose logs -f

# 验证健康检查接口
curl http://127.0.0.1:8000/api/health
```
若返回 `{"status":"ok",...}`，则说明服务已完全正常工作！

---

## 4. 绑定域名与配置 HTTPS 证书

为了让用户更安全、专业地使用（以及避免浏览器对非 HTTPS 域名的限制），建议通过 Nginx 接入域名与免费 SSL 证书。

### 步骤 1：安装 Nginx 与 Certbot
```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 步骤 2：配置 Nginx 站点
复制仓库中预先优化好的配置模板：
```bash
sudo cp deploy/nginx/evocanvas.conf /etc/nginx/conf.d/evocanvas.conf
```
编辑该文件，将其中的 `your-domain.com` 替换为你的真实域名：
```bash
sudo nano /etc/nginx/conf.d/evocanvas.conf
```
测试并重载 Nginx：
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 步骤 3：一键申请并配置免费 HTTPS 证书
确保你的域名已通过 DNS 解析到该服务器公网 IP，然后执行：
```bash
sudo certbot --nginx -d your-domain.com
```
Certbot 会自动完成证书申请、续签配置及 Nginx 443 端口跳转。

现在，任何人访问 `https://your-domain.com` 即可直接进入 EvoCanvas！

---

## 5. 备用部署方式：服务器裸机运行（无 Docker）

如果你希望直接在服务器操作系统上运行原生进程：

### 前置环境要求：
- **Node.js** >= 22.19.0（推荐使用 `nvm` 安装最新 Node 22）
- **Python** 3.10 ~ 3.12 及 `python3-venv`

### 安装与构建：
```bash
cd /opt/evocanvas

# 1. 安装后端依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt

# 2. 安装前端与运行时依赖并编译
npm --prefix frontend install
npm --prefix frontend run build

npm --prefix pi-runtime install
npm --prefix pi-runtime run build

# 3. 准备环境变量
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY
```

### 一键启动脚本：
我们提供了封装好的启停脚本：
```bash
./deploy/start-server.sh
```

### 生产进程常驻（推荐使用 PM2 或 Systemd）：
如果希望断开 SSH 终端后服务仍旧在后台常驻：
```bash
# 全局安装 pm2
npm install -g pm2

# 启动 Pi Runtime
pm2 start pi-runtime/dist/server.js --name evocanvas-runtime

# 启动后端
pm2 start ".venv/bin/uvicorn app.api.server:app --host 127.0.0.1 --port 8000" --name evocanvas-web

# 保存当前进程列表开机自启
pm2 save
pm2 startup
```

---

## 6. 数据持久化与备份

- **数据存储位置**：
  - **AI 会话与卡片 Revision 事务库**：位于 `.pi-storage/`
  - **工作区与上下文**：位于 `workspace-data/`
- **Docker 容器环境**：数据保存在名为 `evocanvas-data` 的 Docker Volume 中，容器更新或重建不会导致数据丢失。
- **定期备份建议**：
  ```bash
  # 备份数据目录
  tar -czvf evocanvas-backup-$(date +%F).tar.gz workspace-data/ .pi-storage/
  ```

---

## 7. 常见问题排查（FAQ）

### Q1: 页面打开空白或加载缓慢？
- 检查 Nginx 是否开启了 Gzip 压缩（`deploy/nginx/evocanvas.conf` 中已默认开启）。
- 检查浏览器控制台是否有静态资源 404 报错，确认 `frontend/dist` 是否已正确编译。

### Q2: 画布发送消息后一直在转圈，无内容流出？
- **原因 1：Nginx 缓冲未关闭**。EvoCanvas 消息采用流式输出（SSE），Nginx 中必须配置 `proxy_buffering off;`，请核对 Nginx 配置。
- **原因 2：未配置有效的大模型 Key**。检查 `.env` 中的 `DEEPSEEK_API_KEY` 是否填写正确且账户有额度。
- **原因 3：Pi Runtime 异常**。通过 `docker compose logs` 或 `pm2 logs evocanvas-runtime` 查看是否有连接超时或 Provider 报错。

### Q3: 如何更换其他大模型（如 OpenAI / Azure / 兼容端点）？
在 `.env` 中修改：
```ini
PI_PROVIDER=openai  # 或兼容端点
PI_MODEL=gpt-4o
OPENAI_API_KEY=sk-xxxx
```
重启服务即可生效。
