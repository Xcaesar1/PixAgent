import uuid

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import delete

from app import events
from app.config import get_settings
from app.db import SessionFactory
from app.main import app
from app.models import User
from app.providers import get_image_provider
from app.queue import close_queue
from app.storage import ensure_bucket

# 测试账号统一此前缀，清理时只删这些行，避免误清开发库里的真实用户
TEST_USER_PREFIX = "test_"
TEST_REDIS_DB = 1


@pytest.fixture(scope="session", autouse=True)
def bucket():
    ensure_bucket()


@pytest.fixture(scope="session", autouse=True)
def mock_provider():
    """测试一律走占位图实现，不受本机 IMAGE_PROVIDER 配置影响，也不产生调用费用。"""
    settings = get_settings()
    original, settings.image_provider = settings.image_provider, "mock"
    get_image_provider.cache_clear()
    yield
    settings.image_provider = original
    get_image_provider.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def corner_matting():
    settings = get_settings()
    original, settings.matting_provider = settings.matting_provider, "corner"
    yield
    settings.matting_provider = original


@pytest.fixture(scope="session", autouse=True)
def skip_ocr():
    settings = get_settings()
    original, settings.ocr_provider = settings.ocr_provider, "none"
    yield
    settings.ocr_provider = original


def _test_redis_url(url: str) -> str:
    head, _, tail = url.rpartition("/")
    return f"{head}/{TEST_REDIS_DB}" if tail.isdigit() else f"{url.rstrip('/')}/{TEST_REDIS_DB}"


@pytest.fixture(scope="session", autouse=True)
async def isolated_redis():
    """测试独占一个 Redis 库。开发中的 worker 只监听默认库，不会抢走测试投递的任务。"""
    settings = get_settings()
    original, settings.redis_url = settings.redis_url, _test_redis_url(settings.redis_url)
    events.redis_client.cache_clear()
    yield
    await close_queue()
    await events.redis_client().aclose()
    settings.redis_url = original
    events.redis_client.cache_clear()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _credentials() -> dict[str, str]:
    return {"username": f"{TEST_USER_PREFIX}{uuid.uuid4().hex[:10]}", "password": "secret123"}


@pytest.fixture
def credentials() -> dict[str, str]:
    return _credentials()


@pytest.fixture
def other_credentials() -> dict[str, str]:
    """第二个账号，用于验证跨用户访问被拒绝。"""
    return _credentials()


@pytest.fixture(autouse=True)
async def cleanup_users():
    yield
    async with SessionFactory() as session:
        await session.execute(delete(User).where(User.username.startswith(TEST_USER_PREFIX)))
        await session.commit()
