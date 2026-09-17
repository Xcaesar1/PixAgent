# PixAgent

<p align="center">
  <img src="assets/branding/pixagent-logo.png" alt="PixAgent Logo" width="320" />
</p>

AI 图片编辑应用，使用自然语言规划编辑步骤，支持画布编辑、图层操作、图片生成、抠图和区域编辑。

## 技术栈

- 前端：React、TypeScript、Konva、Vite。
- 后端：Python 3.13、FastAPI、LangChain、LangGraph。
- 异步任务与存储：ARQ、Redis、PostgreSQL、MinIO。
- 本地图像处理：Pillow、rembg、ONNX Runtime、OpenCV。

## 本地开发

准备 Docker Compose、Python 3.13、uv 和 Node.js 22.12 或更高版本。
以下命令使用 PowerShell，在不同终端中分别启动 API、Worker 和前端。

```powershell
git clone https://github.com/Xcaesar1/PixAgent.git
cd PixAgent
Copy-Item .env.example .env
docker compose up -d
```

默认 `IMAGE_PROVIDER=mock` 使用占位图片。真实云端图片生成和编辑需要配置
`IMAGE_PROVIDER=dashscope` 与 `DASHSCOPE_API_KEY`，可能产生 API 费用。
本地抠图和分割首次运行可能下载模型。

API：

```powershell
cd backend
uv sync --frozen --all-extras
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 7302
```

Worker：

```powershell
cd backend
uv run arq app.worker.WorkerSettings
```

前端：

```powershell
cd frontend
npm ci
npm run dev
```

访问 http://localhost:7301，健康检查地址为 http://localhost:7302/api/health。

## 检查

```powershell
cd backend
uv run pytest
```

```powershell
cd frontend
npm run lint
npm run build
```

## 部署状态

当前为代码仓库初始化，尚未完成 VPS 部署或运行验证。
现有 Compose 包含开发默认凭据和主机端口映射，不应原样用于公网部署。

部署前必须替换数据库、对象存储及 JWT 默认密钥，配置 HTTPS、访问控制、
图片公开访问地址、资源限制和备份。数据库、Redis 和存储管理入口不应暴露公网。
不要提交 `.env`、密钥、上传图片、数据库文件或模型缓存。
