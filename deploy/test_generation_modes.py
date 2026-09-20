"""Run regression tests against an isolated database, never the application DB."""
import asyncio
import os
import subprocess
from urllib.parse import urlsplit, urlunsplit

import asyncpg

TEST_DB = "pixagent_modes_test_20260917"


async def prepare():
    original = os.environ["DATABASE_URL"]
    parts = urlsplit(original.replace("postgresql+asyncpg:", "postgresql:", 1))
    conn = await asyncpg.connect(urlunsplit(parts))
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{TEST_DB}"')
    finally:
        await conn.close()
    os.environ["DATABASE_URL"] = urlunsplit(parts._replace(
        scheme="postgresql+asyncpg", path="/" + TEST_DB
    ))


asyncio.run(prepare())
os.environ.update(APP_ENV="tunnel", REGISTRATION_ENABLED="true", IMAGE_PROVIDER="mock",
                  GENERATION_PROVIDER="", L0VEYOU_TOKEN_FILE="", DASHSCOPE_API_KEY="")
subprocess.run(["alembic", "upgrade", "head"], check=True)
subprocess.run(["uv", "run", "--frozen", "--all-extras", "pytest", "-q"], check=True)
