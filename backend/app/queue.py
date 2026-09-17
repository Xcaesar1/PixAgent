import uuid

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import get_settings

_pool: ArqRedis | None = None


async def queue() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    return _pool


async def close_queue() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def enqueue(task: str, run_id: uuid.UUID) -> None:
    """以 run id 作为任务 ID，重复投递同一 run 不会产生第二次执行。"""
    pool = await queue()
    await pool.enqueue_job(task, run_id, _job_id=str(run_id))
