import json
import uuid

import httpx
import pytest

from app.db import SessionFactory
from app.models.tool_run import RunStatus
from app.services import runs
from app.tasks.tools import run_tool


@pytest.fixture
async def signed_in(client: httpx.AsyncClient, credentials):
    await client.post("/api/auth/register", json=credentials)
    return client


async def start_run(client: httpx.AsyncClient, **overrides) -> dict:
    payload = {"prompt": "浅木色桌面上的白色马克杯", "ratio": "1:1", "count": 4} | overrides
    response = await client.post("/api/generations", json=payload)
    assert response.status_code == 202, response.text
    return response.json()


async def test_generation_is_accepted_as_queued(signed_in: httpx.AsyncClient):
    body = await start_run(signed_in)

    assert body["status"] == "queued"
    assert body["candidates"] == []


async def test_worker_produces_requested_number_of_candidates(signed_in: httpx.AsyncClient):
    run_id = uuid.UUID((await start_run(signed_in, count=2, ratio="4:5"))["id"])

    async with SessionFactory() as session:
        await run_tool({}, run_id)
        run = await runs.load(session, run_id)

    assert run.status is RunStatus.SUCCEEDED
    assert run.progress == 100

    body = (await signed_in.get(f"/api/runs/{run_id}")).json()
    assert len(body["candidates"]) == 2
    assert {(c["width"], c["height"]) for c in body["candidates"]} == {(1080, 1350)}


async def test_finished_run_is_not_executed_twice(signed_in: httpx.AsyncClient):
    run_id = uuid.UUID((await start_run(signed_in, count=1))["id"])

    await run_tool({}, run_id)
    await run_tool({}, run_id)

    body = (await signed_in.get(f"/api/runs/{run_id}")).json()
    assert len(body["candidates"]) == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"prompt": "   "},
        {"prompt": ""},
        {"ratio": "7:3"},
        {"count": 0},
        {"count": 7},
    ],
)
async def test_invalid_parameters_are_rejected(signed_in: httpx.AsyncClient, overrides):
    payload = {"prompt": "马克杯", "ratio": "1:1", "count": 4} | overrides

    response = await signed_in.post("/api/generations", json=payload)

    assert response.status_code == 422


async def test_unknown_reference_asset_is_rejected(signed_in: httpx.AsyncClient):
    response = await signed_in.post(
        "/api/generations",
        json={"prompt": "马克杯", "reference_asset_ids": [str(uuid.uuid4())]},
    )

    assert response.status_code == 404


async def test_run_requires_authentication(client: httpx.AsyncClient):
    assert (await client.post("/api/generations", json={"prompt": "杯子"})).status_code == 401
    assert (await client.get(f"/api/runs/{uuid.uuid4()}")).status_code == 401


async def test_runs_are_isolated_per_user(
    client: httpx.AsyncClient, credentials, other_credentials
):
    await client.post("/api/auth/register", json=credentials)
    run_id = (await start_run(client))["id"]

    await client.post("/api/auth/logout")
    await client.post("/api/auth/register", json=other_credentials)

    assert (await client.get(f"/api/runs/{run_id}")).status_code == 404


async def test_progress_stream_replays_snapshot_then_closes(signed_in: httpx.AsyncClient):
    """已结束的任务也要能拿到终态，页面刷新后才不会一直停在进度条。"""
    run_id = (await start_run(signed_in, count=1))["id"]
    await run_tool({}, uuid.UUID(run_id))

    frames = []
    async with signed_in.stream("GET", f"/events/runs/{run_id}") as stream:
        assert stream.headers["content-type"].startswith("text/event-stream")
        async for line in stream.aiter_lines():
            if line.startswith("data: "):
                frames.append(json.loads(line[6:]))

    assert [frame["status"] for frame in frames] == ["succeeded"]
    assert frames[0]["id"] == run_id
    assert frames[0]["progress"] == 100


async def test_progress_stream_rejects_other_users_run(
    client: httpx.AsyncClient, credentials, other_credentials
):
    await client.post("/api/auth/register", json=credentials)
    run_id = (await start_run(client))["id"]

    await client.post("/api/auth/logout")
    await client.post("/api/auth/register", json=other_credentials)

    assert (await client.get(f"/events/runs/{run_id}")).status_code == 404
