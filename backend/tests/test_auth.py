import httpx

from app.security import SESSION_COOKIE


async def test_register_sets_session_cookie(client: httpx.AsyncClient, credentials):
    response = await client.post("/api/auth/register", json=credentials)

    assert response.status_code == 201
    assert response.json()["username"] == credentials["username"]
    assert SESSION_COOKIE in response.cookies


async def test_register_rejects_duplicate_username(client: httpx.AsyncClient, credentials):
    await client.post("/api/auth/register", json=credentials)

    response = await client.post("/api/auth/register", json=credentials)

    assert response.status_code == 409


async def test_login_then_me_returns_current_user(client: httpx.AsyncClient, credentials):
    await client.post("/api/auth/register", json=credentials)
    await client.post("/api/auth/logout")

    await client.post("/api/auth/login", json=credentials)
    response = await client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["username"] == credentials["username"]


async def test_login_rejects_wrong_password(client: httpx.AsyncClient, credentials):
    await client.post("/api/auth/register", json=credentials)

    response = await client.post(
        "/api/auth/login", json={**credentials, "password": "wrong-password"}
    )

    assert response.status_code == 401


async def test_me_requires_session(client: httpx.AsyncClient):
    response = await client.get("/api/auth/me")

    assert response.status_code == 401


async def test_logout_clears_session(client: httpx.AsyncClient, credentials):
    await client.post("/api/auth/register", json=credentials)

    await client.post("/api/auth/logout")

    assert (await client.get("/api/auth/me")).status_code == 401


async def test_register_validates_username_charset(client: httpx.AsyncClient):
    response = await client.post(
        "/api/auth/register", json={"username": "bad name!", "password": "secret123"}
    )

    assert response.status_code == 422
