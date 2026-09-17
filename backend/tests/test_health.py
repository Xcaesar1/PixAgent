import httpx
import pytest
from httpx import ASGITransport

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_reports_dependencies(client: httpx.AsyncClient):
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"api": "ok", "database": "ok", "storage": "ok"}
