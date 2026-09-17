import uuid

import httpx
import pytest

from tests.canvas import invoke
from tests.test_assets import make_image, upload_payload


@pytest.fixture
async def signed_in(client: httpx.AsyncClient, credentials):
    await client.post("/api/auth/register", json=credentials)
    return client


async def upload(client: httpx.AsyncClient, size=(320, 240), data: bytes | None = None) -> str:
    response = await client.post("/api/assets", files=upload_payload(data or make_image(size)))
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def open_session(client: httpx.AsyncClient, image: bytes | None = None, **overrides) -> dict:
    asset_id = await upload(client, data=image) if image else await upload(client)
    payload = {"current_asset_id": asset_id} | overrides
    response = await client.post("/api/sessions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def test_new_session_starts_at_first_revision(signed_in: httpx.AsyncClient):
    body = await open_session(signed_in, title="  白底 主图  ")

    assert body["title"] == "白底 主图"
    assert body["revision"] == 1
    assert body["original_asset_id"] == body["current_asset_id"]


async def test_document_describes_current_image_as_base_layer(signed_in: httpx.AsyncClient):
    asset_id = await upload(signed_in, (400, 500))

    body = await open_session(signed_in, current_asset_id=asset_id)

    assert (body["document"]["width"], body["document"]["height"]) == (400, 500)
    [layer] = body["document"]["layers"]
    assert (layer["kind"], layer["asset_id"], layer["locked"]) == ("image", asset_id, True)


async def test_blank_title_falls_back_to_placeholder(signed_in: httpx.AsyncClient):
    assert (await open_session(signed_in, title="   "))["title"] == "未命名会话"


async def test_unadopted_candidates_stay_on_the_wall(signed_in: httpx.AsyncClient):
    current = await upload(signed_in)
    others = [await upload(signed_in) for _ in range(2)]

    body = await open_session(signed_in, current_asset_id=current, asset_ids=[current, *others])

    assert [asset["id"] for asset in body["assets"]] == [current, *others]


async def test_switching_current_image_bumps_revision(signed_in: httpx.AsyncClient):
    body = await open_session(signed_in)
    other = await upload(signed_in, (500, 500))

    patched = (
        await signed_in.patch(f"/api/sessions/{body['id']}", json={"current_asset_id": other})
    ).json()

    assert patched["revision"] == 2
    assert patched["current_asset_id"] == other
    assert patched["document"]["width"] == 500
    assert other in [asset["id"] for asset in patched["assets"]]


async def test_switching_to_the_same_image_keeps_revision(signed_in: httpx.AsyncClient):
    body = await open_session(signed_in)

    patched = (
        await signed_in.patch(
            f"/api/sessions/{body['id']}", json={"current_asset_id": body["current_asset_id"]}
        )
    ).json()

    assert patched["revision"] == 1


async def test_picking_the_cropped_image_again_restores_its_full_size(signed_in: httpx.AsyncClient):
    """裁剪只缩小画布、不换资产，点回这张图应当回到原图画幅。"""
    session = await open_session(signed_in)
    cropped = (await invoke(signed_in, session["id"], "crop_canvas", {"ratio": "1:1"}))["session"]
    assert (cropped["document"]["width"], cropped["document"]["height"]) == (240, 240)

    patched = (
        await signed_in.patch(
            f"/api/sessions/{session['id']}",
            json={"current_asset_id": session["current_asset_id"]},
        )
    ).json()

    assert (patched["document"]["width"], patched["document"]["height"]) == (320, 240)
    assert patched["revision"] == cropped["revision"] + 1


async def test_history_records_creation_and_switches(signed_in: httpx.AsyncClient):
    body = await open_session(signed_in)
    other = await upload(signed_in)
    await signed_in.patch(f"/api/sessions/{body['id']}", json={"current_asset_id": other})

    entries = (await signed_in.get(f"/api/sessions/{body['id']}/history")).json()

    assert [entry["action"] for entry in entries] == ["switch_current", "create_session"]
    assert entries[0]["result"]["revision"] == 2


async def test_unknown_asset_is_rejected(signed_in: httpx.AsyncClient):
    response = await signed_in.post("/api/sessions", json={"current_asset_id": str(uuid.uuid4())})

    assert response.status_code == 404


async def test_session_requires_authentication(client: httpx.AsyncClient):
    assert (await client.get("/api/sessions")).status_code == 401
    assert (await client.get(f"/api/sessions/{uuid.uuid4()}")).status_code == 401


async def test_sessions_are_isolated_per_user(
    client: httpx.AsyncClient, credentials, other_credentials
):
    await client.post("/api/auth/register", json=credentials)
    session_id = (await open_session(client))["id"]

    await client.post("/api/auth/logout")
    await client.post("/api/auth/register", json=other_credentials)

    assert (await client.get(f"/api/sessions/{session_id}")).status_code == 404
    assert (await client.get("/api/sessions")).json() == []
