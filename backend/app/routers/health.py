import asyncio
from collections.abc import Awaitable

from fastapi import APIRouter
from sqlalchemy import text

from app import storage
from app.db import SessionDep

router = APIRouter(prefix="/health", tags=["health"])


async def _probe(awaitable: Awaitable) -> str:
    try:
        await awaitable
        return "ok"
    except Exception as exc:  # noqa: BLE001 - 健康检查需要报告任意故障原因
        return f"error: {type(exc).__name__}"


@router.get("")
async def health(session: SessionDep) -> dict[str, str]:
    database, object_storage = await asyncio.gather(
        _probe(session.execute(text("select 1"))),
        _probe(asyncio.to_thread(storage.ensure_bucket)),
    )
    return {"api": "ok", "database": database, "storage": object_storage}
