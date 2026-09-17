import io
import json
import zipfile
from urllib.parse import unquote

import httpx
import pytest
from PIL import Image

from tests.canvas import apply, invoke
from tests.test_sessions import open_session


@pytest.fixture
async def signed_in(client: httpx.AsyncClient, credentials):
    await client.post("/api/auth/register", json=credentials)
    return client


def _zip_of(response: httpx.Response) -> zipfile.ZipFile:
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/zip")
    return zipfile.ZipFile(io.BytesIO(response.content))


async def test_export_without_materials_includes_current_canvas(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in, title="白底主图")

    response = await signed_in.post(f"/api/sessions/{session['id']}/exports", json={})
    archive = _zip_of(response)
    names = archive.namelist()
    manifest = json.loads(archive.read("manifest.json"))

    disposition = unquote(response.headers["content-disposition"])
    assert "filename*=UTF-8''" in response.headers["content-disposition"]
    assert "白底主图" in disposition
    assert manifest["title"] == "白底主图"
    assert len(manifest["items"]) == 1
    assert manifest["items"][0]["kind"] == "canvas"
    assert manifest["items"][0]["file"] in names


async def test_export_packs_delivery_sizes_and_manifest(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in)
    updated = await apply(signed_in, session["id"], "prepare_delivery_sizes")
    exported = [asset for asset in updated["assets"] if asset["kind"] == "export"]

    response = await signed_in.post(f"/api/sessions/{session['id']}/exports", json={})
    archive = _zip_of(response)
    manifest = json.loads(archive.read("manifest.json"))
    items = manifest["items"]
    ratios = {item["ratio"] for item in items}

    assert {item["kind"] for item in items} == {"export"}
    assert ratios == {"1:1", "4:5", "9:16"}
    assert {item["asset_id"] for item in items} == {asset["id"] for asset in exported}
    assert set(archive.namelist()) == {"manifest.json", *[item["file"] for item in items]}


async def test_export_current_uses_flattened_canvas(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in)
    await invoke(signed_in, session["id"], "flip_layer", {"direction": "horizontal"})

    response = await signed_in.post(
        f"/api/sessions/{session['id']}/exports",
        json={"asset_ids": [session["current_asset_id"]]},
    )
    archive = _zip_of(response)
    manifest = json.loads(archive.read("manifest.json"))
    image = Image.open(io.BytesIO(archive.read(manifest["items"][0]["file"])))

    assert manifest["items"][0]["kind"] == "canvas"
    assert image.size == (session["document"]["width"], session["document"]["height"])


async def test_export_rejects_asset_outside_session(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in)
    other = await open_session(signed_in)
    foreign = other["current_asset_id"]

    response = await signed_in.post(
        f"/api/sessions/{session['id']}/exports", json={"asset_ids": [foreign]}
    )
    assert response.status_code == 422


async def test_export_is_denied_to_other_users(
    client: httpx.AsyncClient, credentials, other_credentials
):
    await client.post("/api/auth/register", json=credentials)
    session = await open_session(client)
    await client.post("/api/auth/logout")
    await client.post("/api/auth/register", json=other_credentials)

    response = await client.post(f"/api/sessions/{session['id']}/exports", json={})
    assert response.status_code == 404
