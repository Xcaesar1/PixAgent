import uuid

from app.db import SessionFactory
from app.services import runs, tools


async def run_tool(_: dict, run_id: uuid.UUID) -> None:
    async with SessionFactory() as session:
        try:
            run = await runs.load(session, run_id)
        except runs.RunNotFound:
            return
        # 队列重投或 worker 重启后的重复消费不应二次扣费
        if run.status.is_terminal:
            return

        await tools.execute(session, run)
