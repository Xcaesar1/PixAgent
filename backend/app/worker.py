from arq.connections import RedisSettings

from app.config import get_settings
from app.tasks import TASKS

settings = get_settings()


class WorkerSettings:
    """ARQ worker 入口。新增异步任务需在 app.tasks.TASKS 中注册。"""

    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = TASKS
    max_jobs = settings.worker_max_jobs
    # Four sequential GPT tasks include polling, download and persistence time.
    job_timeout = 1200
    keep_result = 3600
