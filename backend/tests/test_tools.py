import uuid

import httpx
import pytest
from langchain_core.messages import AIMessage

from app.agent import graph
from app.tasks.tools import run_tool
from tests.canvas import apply, error_of, invoke, layers, scene, select
from tests.test_agent import FakePlanner
from tests.test_sessions import open_session, upload


@pytest.fixture
async def signed_in(client: httpx.AsyncClient, credentials):
    await client.post("/api/auth/register", json=credentials)
    return client


async def test_flip_updates_document_immediately(signed_in: httpx.AsyncClient):
    session_id = (await open_session(signed_in))["id"]

    body = await invoke(signed_in, session_id, "flip_layer", {"direction": "horizontal"})

    assert body["run"]["status"] == "succeeded"
    assert body["session"]["document"]["layers"][0]["transform"]["scale_x"] == -1
    assert body["session"]["revision"] == 2
    assert body["session"]["can_undo"] is True


async def test_crop_to_square_changes_canvas(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in)

    body = await invoke(signed_in, session["id"], "crop_canvas", {"ratio": "1:1"})
    document = body["session"]["document"]

    assert document["width"] == document["height"] == 240
    assert document["layers"][0]["transform"]["x"] == -40


async def test_opacity_and_scale_and_rotate(signed_in: httpx.AsyncClient):
    session_id = (await open_session(signed_in))["id"]

    await invoke(signed_in, session_id, "set_layer_opacity", {"opacity": 0.6})
    await invoke(signed_in, session_id, "scale_layer", {"factor": 0.5})
    body = await invoke(signed_in, session_id, "rotate_layer", {"angle": 15})

    layer = body["session"]["document"]["layers"][0]
    assert layer["opacity"] == 0.6
    assert layer["transform"]["scale_x"] == 0.5
    assert layer["transform"]["rotation"] == 15


async def test_set_layer_text_requires_a_text_layer(signed_in: httpx.AsyncClient):
    session_id = (await open_session(signed_in))["id"]

    body = await invoke(signed_in, session_id, "set_layer_text", {"text": "新品"})

    assert body["run"]["status"] == "failed"
    assert "文字" in (body["run"]["error"] or "")


async def test_set_layer_visible_hides_and_shows(signed_in: httpx.AsyncClient):
    session_id = (await open_session(signed_in))["id"]

    hidden = await invoke(
        signed_in, session_id, "set_layer_visible", {"layer_id": "base", "visible": False}
    )
    assert hidden["session"]["document"]["layers"][0]["visible"] is False

    shown = await invoke(
        signed_in, session_id, "set_layer_visible", {"layer_id": "base", "visible": True}
    )
    assert shown["session"]["document"]["layers"][0]["visible"] is True


async def test_undo_restores_previous_document_and_redo_replays(
    signed_in: httpx.AsyncClient,
):
    session_id = (await open_session(signed_in))["id"]
    await invoke(signed_in, session_id, "flip_layer", {"direction": "vertical"})

    undone = (await signed_in.post(f"/api/sessions/{session_id}/undo")).json()
    assert undone["document"]["layers"][0]["transform"]["scale_y"] == 1
    assert undone["can_undo"] is False
    assert undone["can_redo"] is True

    redone = (await signed_in.post(f"/api/sessions/{session_id}/redo")).json()
    assert redone["document"]["layers"][0]["transform"]["scale_y"] == -1
    assert redone["can_redo"] is False


async def test_new_edit_after_undo_drops_redo_branch(signed_in: httpx.AsyncClient):
    session_id = (await open_session(signed_in))["id"]
    await invoke(signed_in, session_id, "flip_layer", {"direction": "horizontal"})
    await signed_in.post(f"/api/sessions/{session_id}/undo")
    await invoke(signed_in, session_id, "rotate_layer", {"angle": 10})

    session = (await signed_in.get(f"/api/sessions/{session_id}")).json()
    assert session["can_redo"] is False
    assert session["document"]["layers"][0]["transform"]["rotation"] == 10
    assert session["document"]["layers"][0]["transform"]["scale_x"] == 1


async def test_undo_at_start_is_rejected(signed_in: httpx.AsyncClient):
    session_id = (await open_session(signed_in))["id"]

    response = await signed_in.post(f"/api/sessions/{session_id}/undo")

    assert response.status_code == 409


async def test_noop_edit_does_not_append_history(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in)

    body = await invoke(signed_in, session["id"], "set_layer_visible", {"visible": True})
    entries = (await signed_in.get(f"/api/sessions/{session['id']}/history")).json()

    assert body["session"]["revision"] == 1
    assert body["session"]["can_undo"] is False
    assert [entry["action"] for entry in entries] == ["create_session"]


async def test_noop_edit_keeps_redo_branch(signed_in: httpx.AsyncClient):
    session_id = (await open_session(signed_in))["id"]
    await invoke(signed_in, session_id, "flip_layer", {"direction": "horizontal"})
    await signed_in.post(f"/api/sessions/{session_id}/undo")
    await invoke(signed_in, session_id, "set_layer_visible", {"visible": True})

    session = (await signed_in.get(f"/api/sessions/{session_id}")).json()
    assert session["can_redo"] is True

    redone = (await signed_in.post(f"/api/sessions/{session_id}/redo")).json()
    assert redone["document"]["layers"][0]["transform"]["scale_x"] == -1


async def test_unknown_and_invalid_tools_are_rejected(signed_in: httpx.AsyncClient):
    session_id = (await open_session(signed_in))["id"]

    unknown = await signed_in.post(
        f"/api/sessions/{session_id}/tools", json={"tool": "explode", "params": {}}
    )
    invalid = await signed_in.post(
        f"/api/sessions/{session_id}/tools",
        json={"tool": "crop_canvas", "params": {}},
    )

    assert unknown.status_code == 404
    assert invalid.status_code == 422


async def test_remove_background_adopts_transparent_result(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in)
    body = await invoke(signed_in, session["id"], "remove_background")
    run_id = uuid.UUID(body["run"]["id"])

    await run_tool({}, run_id)
    updated = (await signed_in.get(f"/api/sessions/{session['id']}")).json()
    current = next(
        asset for asset in updated["assets"] if asset["id"] == updated["current_asset_id"]
    )

    assert updated["revision"] == 2
    assert current["has_alpha"] is True
    assert current["id"] != session["current_asset_id"]


async def test_adjust_image_adopts_a_new_asset(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in)
    body = await invoke(signed_in, session["id"], "adjust_image", {"brightness": 0.3})

    await run_tool({}, uuid.UUID(body["run"]["id"]))
    updated = (await signed_in.get(f"/api/sessions/{session['id']}")).json()

    assert updated["current_asset_id"] != session["current_asset_id"]
    assert updated["can_undo"] is True


async def test_agent_can_dispatch_a_canvas_tool(signed_in: httpx.AsyncClient, monkeypatch):
    fake = FakePlanner(
        AIMessage(
            content="",
            tool_calls=[{"name": "flip_layer", "args": {"direction": "horizontal"}, "id": "c1"}],
        )
    )
    monkeypatch.setattr(graph, "planner", lambda: fake)
    session_id = (await open_session(signed_in))["id"]

    turn = (
        await signed_in.post(f"/api/sessions/{session_id}/messages", json={"text": "水平翻转"})
    ).json()
    session = (await signed_in.get(f"/api/sessions/{session_id}")).json()

    assert turn["steps"][0]["tool"] == "flip_layer"
    assert session["document"]["layers"][0]["transform"]["scale_x"] == -1


async def test_session_tool_requires_authentication(client: httpx.AsyncClient):
    path = f"/api/sessions/{uuid.uuid4()}/tools"
    payload = {"tool": "flip_layer", "params": {"direction": "horizontal"}}
    assert (await client.post(path, json=payload)).status_code == 401


async def test_replace_background_adopts_single_result(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in)
    body = await invoke(
        signed_in, session["id"], "replace_background", {"prompt": "浅木色桌面"}
    )

    await run_tool({}, uuid.UUID(body["run"]["id"]))
    updated = (await signed_in.get(f"/api/sessions/{session['id']}")).json()
    current = next(
        asset for asset in updated["assets"] if asset["id"] == updated["current_asset_id"]
    )

    assert updated["current_asset_id"] != session["current_asset_id"]
    assert updated["revision"] == 2
    assert (current["width"], current["height"]) == (320, 240)


async def test_replace_background_candidates_stay_on_the_wall(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in)
    body = await invoke(
        signed_in,
        session["id"],
        "replace_background",
        {"prompt": "浅木色桌面", "count": 2},
    )

    await run_tool({}, uuid.UUID(body["run"]["id"]))
    updated = (await signed_in.get(f"/api/sessions/{session['id']}")).json()
    generated = [asset for asset in updated["assets"] if asset["kind"] == "generated"]
    entries = (await signed_in.get(f"/api/sessions/{session['id']}/history")).json()

    assert updated["current_asset_id"] == session["current_asset_id"]
    assert updated["revision"] == 1
    assert len(generated) == 2
    # 画布没变所以修订号不涨，但这次生成要出现在编辑记录里
    assert [entry["action"] for entry in entries] == ["replace_background", "create_session"]


async def test_expand_canvas_grows_to_cover_ratio(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in)
    body = await invoke(signed_in, session["id"], "expand_canvas", {"ratio": "16:9"})

    await run_tool({}, uuid.UUID(body["run"]["id"]))
    updated = (await signed_in.get(f"/api/sessions/{session['id']}")).json()
    current = next(
        asset for asset in updated["assets"] if asset["id"] == updated["current_asset_id"]
    )

    assert updated["current_asset_id"] != session["current_asset_id"]
    assert (updated["document"]["width"], updated["document"]["height"]) == (426, 240)
    assert (current["width"], current["height"]) == (426, 240)


async def test_expanding_a_split_canvas_only_fills_the_wall(signed_in: httpx.AsyncClient):
    """已拆层时扩图不写回画布，但编辑记录要能对上图片墙里多出来的那张。"""
    session = await open_session(signed_in, image=scene())
    split = await apply(signed_in, session["id"], "split_layers")

    body = await invoke(signed_in, session["id"], "expand_canvas", {"ratio": "16:9"})
    await run_tool({}, uuid.UUID(body["run"]["id"]))
    updated = (await signed_in.get(f"/api/sessions/{session['id']}")).json()
    entries = (await signed_in.get(f"/api/sessions/{session['id']}/history")).json()

    assert updated["document"] == split["document"]
    assert updated["revision"] == split["revision"]
    assert entries[0]["action"] == "expand_canvas"


async def test_upscale_image_raises_resolution(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in)
    body = await invoke(signed_in, session["id"], "upscale_image", {"scale": 2})

    await run_tool({}, uuid.UUID(body["run"]["id"]))
    updated = (await signed_in.get(f"/api/sessions/{session['id']}")).json()
    current = next(
        asset for asset in updated["assets"] if asset["id"] == updated["current_asset_id"]
    )

    assert updated["current_asset_id"] != session["current_asset_id"]
    assert (updated["document"]["width"], updated["document"]["height"]) == (640, 480)
    assert (current["width"], current["height"]) == (640, 480)


async def test_preparing_point_selection_is_accepted(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in)
    response = await signed_in.post(f"/api/sessions/{session['id']}/selection/prepare")
    assert response.status_code == 204


async def test_point_selection_is_bound_to_revision(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in)
    body = await select(
        signed_in, session["id"], session["revision"], points=[{"x": 0.5, "y": 0.5}]
    )

    assert body["revision"] == session["revision"]
    assert body["mask"]["kind"] == "mask"
    assert body["markers"] == [{"index": 1, "x": 0.5, "y": 0.5}]

    stale = await signed_in.post(
        f"/api/sessions/{session['id']}/selection",
        json={"revision": 99, "points": [{"x": 0.2, "y": 0.2}]},
    )
    assert stale.status_code == 409


async def test_brush_selection_creates_a_mask(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in)
    body = await select(
        signed_in,
        session["id"],
        session["revision"],
        strokes=[[{"x": 0.2, "y": 0.2}, {"x": 0.8, "y": 0.8}]],
    )

    assert body["mask"]["has_alpha"] is True


async def test_erase_region_adopts_masked_result(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in)
    selected = await select(
        signed_in, session["id"], session["revision"], points=[{"x": 0.5, "y": 0.5}]
    )
    body = await invoke(
        signed_in,
        session["id"],
        "erase_region",
        {"mask_asset_id": selected["mask"]["id"], "revision": session["revision"]},
    )

    await run_tool({}, uuid.UUID(body["run"]["id"]))
    updated = (await signed_in.get(f"/api/sessions/{session['id']}")).json()

    assert updated["current_asset_id"] != session["current_asset_id"]
    assert updated["revision"] == 2
    assert (await signed_in.get(f"/api/sessions/{session['id']}/selection")).json() is None


async def test_replace_region_requires_a_prompt_and_honors_the_selection(
    signed_in: httpx.AsyncClient,
):
    session = await open_session(signed_in)
    missing = await signed_in.post(
        f"/api/sessions/{session['id']}/tools",
        json={"tool": "replace_region", "params": {}},
    )
    assert missing.status_code == 422

    selected = await select(
        signed_in, session["id"], session["revision"], points=[{"x": 0.4, "y": 0.6}]
    )
    body = await invoke(
        signed_in,
        session["id"],
        "replace_region",
        {
            "prompt": "换成陶瓷杯",
            "mask_asset_id": selected["mask"]["id"],
            "revision": session["revision"],
        },
    )
    await run_tool({}, uuid.UUID(body["run"]["id"]))
    updated = (await signed_in.get(f"/api/sessions/{session['id']}")).json()
    assert updated["current_asset_id"] != session["current_asset_id"]


async def test_split_layers_replaces_base_with_subject_and_background(
    signed_in: httpx.AsyncClient,
):
    session = await open_session(signed_in, image=scene())
    body = await invoke(signed_in, session["id"], "split_layers")
    await run_tool({}, uuid.UUID(body["run"]["id"]))
    updated = (await signed_in.get(f"/api/sessions/{session['id']}")).json()
    ids = [layer["id"] for layer in updated["document"]["layers"]]

    assert ids[:2] == ["background", "subject"]
    assert all(not layer_id.startswith("text-") for layer_id in ids)
    assert updated["revision"] == 2
    assert updated["current_asset_id"] == session["current_asset_id"]

    again = await invoke(signed_in, session["id"], "split_layers")
    await run_tool({}, uuid.UUID(again["run"]["id"]))
    repeated = (await signed_in.get(f"/api/sessions/{session['id']}")).json()
    entries = (await signed_in.get(f"/api/sessions/{session['id']}/history")).json()
    assert [layer["id"] for layer in repeated["document"]["layers"]] == ids
    assert repeated["revision"] == updated["revision"]
    assert [entry["action"] for entry in entries] == ["split_layers", "create_session"]


async def test_switching_back_after_split_restoreslayers(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in, image=scene())
    split = await invoke(signed_in, session["id"], "split_layers")
    await run_tool({}, uuid.UUID(split["run"]["id"]))
    after_split = (await signed_in.get(f"/api/sessions/{session['id']}")).json()
    other = await upload(signed_in, (400, 300))

    away = (
        await signed_in.patch(f"/api/sessions/{session['id']}", json={"current_asset_id": other})
    ).json()
    back = (
        await signed_in.patch(
            f"/api/sessions/{session['id']}",
            json={"current_asset_id": after_split["current_asset_id"]},
        )
    ).json()

    assert [layer["id"] for layer in away["document"]["layers"]] == ["base"]
    assert back["document"]["layers"] == after_split["document"]["layers"]
    assert back["current_asset_id"] == after_split["current_asset_id"]


async def test_promote_object_creates_a_layer_and_is_idempotent(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in, image=scene())
    selected = await select(
        signed_in, session["id"], session["revision"], points=[{"x": 0.5, "y": 0.5}]
    )
    body = await invoke(
        signed_in,
        session["id"],
        "promote_object_to_layer",
        {"mask_asset_id": selected["mask"]["id"], "revision": session["revision"]},
    )
    await run_tool({}, uuid.UUID(body["run"]["id"]))
    updated = (await signed_in.get(f"/api/sessions/{session['id']}")).json()
    ids = [layer["id"] for layer in updated["document"]["layers"]]

    assert ids[0] == "background"
    assert any(layer_id.startswith("object-") for layer_id in ids)
    assert (await signed_in.get(f"/api/sessions/{session['id']}/selection")).json() is None

    selected = await select(
        signed_in, updated["id"], updated["revision"], points=[{"x": 0.5, "y": 0.5}]
    )
    again = await invoke(
        signed_in,
        session["id"],
        "promote_object_to_layer",
        {"mask_asset_id": selected["mask"]["id"], "revision": updated["revision"]},
    )
    await run_tool({}, uuid.UUID(again["run"]["id"]))
    repeated = (await signed_in.get(f"/api/sessions/{session['id']}")).json()
    assert len(repeated["document"]["layers"]) == len(updated["document"]["layers"])


async def test_move_layer_shifts_position(signed_in: httpx.AsyncClient):
    session_id = (await open_session(signed_in))["id"]
    body = await invoke(signed_in, session_id, "move_layer", {"dx": 18, "dy": -6})
    transform = body["session"]["document"]["layers"][0]["transform"]
    assert (transform["x"], transform["y"]) == (18, -6)


@pytest.mark.parametrize(
    ("tool", "params"),
    [
        ("replace_background", {"prompt": "海边沙滩"}),
        ("expand_canvas", {"ratio": "16:9"}),
        ("upscale_image", {"scale": 2}),
    ],
)
async def test_generate_after_split_stays_on_the_wall(
    signed_in: httpx.AsyncClient, tool: str, params: dict
):
    session = await open_session(signed_in, image=scene())
    split = await invoke(signed_in, session["id"], "split_layers")
    await run_tool({}, uuid.UUID(split["run"]["id"]))
    before = (await signed_in.get(f"/api/sessions/{session['id']}")).json()

    body = await invoke(signed_in, session["id"], tool, params)
    await run_tool({}, uuid.UUID(body["run"]["id"]))
    after = (await signed_in.get(f"/api/sessions/{session['id']}")).json()
    generated = [asset for asset in after["assets"] if asset["kind"] == "generated"]

    assert after["document"]["layers"] == before["document"]["layers"]
    assert after["revision"] == before["revision"]
    assert after["current_asset_id"] == before["current_asset_id"]
    assert len(generated) == 1


async def _split_scene(client: httpx.AsyncClient) -> tuple[dict, dict]:
    """拆好层的会话，连同拆完那一刻的图层表，供图层×选区组合断言比对。"""
    session = await open_session(client, image=scene())
    return session, await apply(client, session["id"], "split_layers")


@pytest.mark.parametrize("layer_id", [None, "subject", "主体"])
async def test_replace_region_without_selection_changes_the_whole_layer(
    signed_in: httpx.AsyncClient, layer_id: str | None
):
    """没有选区就改整层：不点名时落在最上层图像，点名可以用 id 也可以用图层名。"""
    session, before = await _split_scene(signed_in)
    params = {"prompt": "改成红色"} | ({"layer_id": layer_id} if layer_id else {})

    after = await apply(signed_in, session["id"], "replace_region", params)

    assert layers(after)["subject"]["asset_id"] != layers(before)["subject"]["asset_id"]
    assert layers(after)["background"]["asset_id"] == layers(before)["background"]["asset_id"]


async def test_replace_region_with_layer_and_selection_takes_the_overlap(
    signed_in: httpx.AsyncClient,
):
    session, before = await _split_scene(signed_in)
    selected = await select(
        signed_in, session["id"], before["revision"], points=[{"x": 0.5, "y": 0.5}]
    )

    after = await apply(
        signed_in,
        session["id"],
        "replace_region",
        {
            "prompt": "改成红色",
            "layer_id": "background",
            "mask_asset_id": selected["mask"]["id"],
            "revision": before["revision"],
        },
    )

    assert layers(after)["background"]["asset_id"] != layers(before)["background"]["asset_id"]
    assert layers(after)["subject"]["asset_id"] == layers(before)["subject"]["asset_id"]


async def test_selection_missing_the_named_layer_is_refused(signed_in: httpx.AsyncClient):
    """选区与图层没有交集时明确报错，不静默改整层。"""
    session = await open_session(signed_in, image=scene())
    picked = await select(
        signed_in, session["id"], session["revision"], points=[{"x": 0.5, "y": 0.5}]
    )
    updated = await apply(
        signed_in,
        session["id"],
        "promote_object_to_layer",
        {"mask_asset_id": picked["mask"]["id"], "revision": session["revision"]},
    )
    object_id = next(layer_id for layer_id in layers(updated) if layer_id.startswith("object-"))

    elsewhere = await select(
        signed_in, session["id"], updated["revision"], points=[{"x": 0.03, "y": 0.03}]
    )
    body = await invoke(
        signed_in,
        session["id"],
        "replace_region",
        {
            "prompt": "改成红色",
            "layer_id": object_id,
            "mask_asset_id": elsewhere["mask"]["id"],
            "revision": updated["revision"],
        },
    )
    await run_tool({}, uuid.UUID(body["run"]["id"]))
    after = (await signed_in.get(f"/api/sessions/{session['id']}")).json()

    assert "没有覆盖" in await error_of(signed_in, body["run"]["id"])
    assert layers(after)[object_id]["asset_id"] == layers(updated)[object_id]["asset_id"]


async def test_unknown_layer_name_is_refused(signed_in: httpx.AsyncClient):
    session, _ = await _split_scene(signed_in)

    body = await invoke(
        signed_in,
        session["id"],
        "replace_region",
        {"prompt": "改成红色", "layer_id": "不存在的层"},
    )
    await run_tool({}, uuid.UUID(body["run"]["id"]))

    assert "图层不存在" in await error_of(signed_in, body["run"]["id"])


async def test_corner_scale_writes_position_and_undo_restores_both(signed_in: httpx.AsyncClient):
    session_id = (await open_session(signed_in))["id"]

    body = await invoke(
        signed_in, session_id, "scale_layer", {"scale_x": 2, "scale_y": 2, "x": -80, "y": -60}
    )
    scaled = body["session"]["document"]["layers"][0]["transform"]
    assert (scaled["scale_x"], scaled["x"], scaled["y"]) == (2, -80, -60)

    undone = (await signed_in.post(f"/api/sessions/{session_id}/undo")).json()
    back = undone["document"]["layers"][0]["transform"]
    assert (back["scale_x"], back["x"], back["y"]) == (1, 0, 0)

    redone = (await signed_in.post(f"/api/sessions/{session_id}/redo")).json()
    again = redone["document"]["layers"][0]["transform"]
    assert (again["scale_x"], again["x"], again["y"]) == (2, -80, -60)


async def test_adjust_after_split_only_changes_the_target_layer(signed_in: httpx.AsyncClient):
    session, before = await _split_scene(signed_in)
    after = await apply(
        signed_in, session["id"], "adjust_image", {"brightness": 0.4, "layer_id": "subject"}
    )

    assert layers(after)["background"]["asset_id"] == layers(before)["background"]["asset_id"]
    assert layers(after)["subject"]["asset_id"] != layers(before)["subject"]["asset_id"]


async def test_generate_marketing_stays_on_the_wall(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in)
    updated = await apply(signed_in, session["id"], "generate_marketing", {"kind": "product"})
    marketing = [asset for asset in updated["assets"] if asset["kind"] == "marketing"]

    assert updated["current_asset_id"] == session["current_asset_id"]
    assert updated["revision"] == 1
    assert len(marketing) == 1
    assert (marketing[0]["width"], marketing[0]["height"]) == (1080, 1080)


async def test_prepare_delivery_sizes_covers_three_ratios(signed_in: httpx.AsyncClient):
    session = await open_session(signed_in)
    updated = await apply(signed_in, session["id"], "prepare_delivery_sizes")
    exported = [asset for asset in updated["assets"] if asset["kind"] == "export"]
    sizes = {(asset["width"], asset["height"]) for asset in exported}

    assert updated["current_asset_id"] == session["current_asset_id"]
    assert updated["revision"] == 1
    assert sizes == {(1080, 1080), (1080, 1350), (1080, 1920)}
