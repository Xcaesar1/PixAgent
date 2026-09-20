import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app import storage
from app.config import get_settings
from app.queue import close_queue
from app.routers import assets, auth, batches, events, health, runs, sessions

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await asyncio.to_thread(storage.ensure_bucket)
    yield
    await close_queue()


app = FastAPI(
    title="AI 修图智能体",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

api = APIRouter(prefix="/api")
api.include_router(health.router)
api.include_router(auth.router)
api.include_router(assets.router)
api.include_router(runs.router)
api.include_router(sessions.router)
api.include_router(batches.router)
app.include_router(api)

# SSE 不挂在 /api 下，便于反向代理单独关闭缓冲
app.include_router(events.router)

# 生产环境下前端与 API 同源，静态产物由本服务托管；开发环境走 Vite dev proxy。
if settings.frontend_dist.is_dir():
    @app.get("/auth", include_in_schema=False)
    @app.get("/create", include_in_schema=False)
    @app.get("/editor", include_in_schema=False)
    @app.get("/editor/{session_id}", include_in_schema=False)
    @app.get("/marketing", include_in_schema=False)
    @app.get("/marketing/{session_id}", include_in_schema=False)
    @app.get("/batch", include_in_schema=False)
    @app.get("/batch/{run_id}", include_in_schema=False)
    @app.get("/candidates/{run_id}", include_in_schema=False)
    async def frontend_page():
        return FileResponse(settings.frontend_dist / "index.html")

    app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
