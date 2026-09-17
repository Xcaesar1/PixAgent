import io
import uuid
import zipfile

import httpx
import pytest

from app.tasks.tools import run_tool
from tests.test_sessions import upload


@pytest.fixture
async def signed_in(client: httpx.AsyncClient, credentials):
    await client.post("/api/auth/register", json=credentials)
    return client


async def start_batch(
    client: httpx.AsyncClient, asset_ids: list[str], operations: list[dict], **extra
):
    payload = {"asset_ids": asset_ids, "operations": operations, **extra}
    response = await client.post("/api/batches", json=payload)
    assert response.status_code == 202, response.text
    return response.json()


async def test_batch_remove_background_writes_export_assets(signed_in: httpx.AsyncClient):
    ids = [await upload(signed_in), await upload(signed_in, (400, 300))]
    run = await start_batch(
        signed_in, ids, [{"tool": "remove_background", "params": {}}], formats=["png"]
    )
    await run_tool({}, uuid.UUID(run["id"]))

    body = (await signed_in.get(f"/api/batches/{run['id']}")).json()
    assert body["run"]["status"] == "succeeded"
    assert len(body["items"]) == 2
    assert all(item["status"] == "succeeded" for item in body["items"])
    assert all(len(item["outputs"]) == 1 for item in body["items"])
    assert all(item["outputs"][0]["kind"] == "export" for item in body["items"])


async def test_batch_delivery_sizes_and_zip(signed_in: httpx.AsyncClient):
    asset_id = await upload(signed_in)
    run = await start_batch(
        signed_in,
        [asset_id],
        [{"tool": "prepare_delivery_sizes", "params": {}}],
        formats=["png"],
    )
    await run_tool({}, uuid.UUID(run["id"]))

    body = (await signed_in.get(f"/api/batches/{run['id']}")).json()
    sizes = {(item["width"], item["height"]) for item in body["items"][0]["outputs"]}
    assert sizes == {(1080, 1080), (1080, 1350), (1080, 1920)}

    packed = await signed_in.get(f"/api/batches/{run['id']}/export")
    assert packed.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(packed.content))
    assert len([name for name in archive.namelist() if name.startswith("images/")]) == 3


async def test_batch_rejects_unknown_tool(signed_in: httpx.AsyncClient):
    asset_id = await upload(signed_in)
    response = await signed_in.post(
        "/api/batches",
        json={
            "asset_ids": [asset_id],
            "operations": [{"tool": "split_layers", "params": {}}],
        },
    )
    assert response.status_code == 422


async def test_batch_rejects_foreign_asset(
    client: httpx.AsyncClient, credentials, other_credentials
):
    await client.post("/api/auth/register", json=credentials)
    asset_id = await upload(client)
    await client.post("/api/auth/logout")
    await client.post("/api/auth/register", json=other_credentials)

    response = await client.post(
        "/api/batches",
        json={"asset_ids": [asset_id], "operations": [{"tool": "remove_background"}]},
    )
    assert response.status_code == 404


async def test_batch_list_returns_recent_jobs(signed_in: httpx.AsyncClient):
    asset_id = await upload(signed_in)
    run = await start_batch(signed_in, [asset_id], [{"tool": "remove_background"}])
    await run_tool({}, uuid.UUID(run["id"]))

    body = (await signed_in.get("/api/batches")).json()
    assert body[0]["run"]["id"] == run["id"]
