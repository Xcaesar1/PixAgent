import uuid

import httpx
import pytest
from langchain_core.messages import AIMessage

from app.agent import graph
from app.agent.llm import planner
from app.config import get_settings
from app.tasks.tools import run_tool
from tests.canvas import apply, error_of, layers, scene, select, settle
from tests.test_sessions import open_session

PROMPT = {"prompt": "浅木色桌面上的白色马克杯", "ratio": "1:1", "count": 2}


class FakePlanner:
    def __init__(self, message: AIMessage) -> None:
        self._message = message

    async def ainvoke(self, messages):
        self.messages = messages
        return self._message


@pytest.fixture
def fake_planner(monkeypatch):
    def install(message: AIMessage) -> FakePlanner:
        fake = FakePlanner(message)
        monkeypatch.setattr(graph, "planner", lambda: fake)
        return fake

    return install


def tool_call(name: str, args: dict) -> AIMessage:
    return tool_calls((name, args))


def tool_calls(*pairs: tuple[str, dict]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": f"call_{index}"}
            for index, (name, args) in enumerate(pairs, start=1)
        ],
    )


@pytest.fixture
async def signed_in(client: httpx.AsyncClient, credentials):
    await client.post("/api/auth/register", json=credentials)
    return client


async def send(client: httpx.AsyncClient, session_id: str, text: str) -> dict:
    response = await client.post(f"/api/sessions/{session_id}/messages", json={"text": text})
    assert response.status_code == 201, response.text
    return response.json()


async def test_tool_call_is_planned_and_dispatched(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(tool_call("generate_image", PROMPT))
    session_id = (await open_session(signed_in))["id"]

    turn = await send(signed_in, session_id, "换一张白底马克杯")

    assert turn["status"] == "running"
    assert [step["tool"] for step in turn["steps"]] == ["generate_image"]
    assert turn["steps"][0]["label"] == "生成图片"
    assert turn["steps"][0]["run_id"]
    assert "没太理解" not in turn["reply"]
    assert "生成图片" in turn["reply"]


async def test_marketing_tool_is_planned_and_dispatched(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(tool_call("generate_marketing", {"kind": "product"}))
    session_id = (await open_session(signed_in))["id"]

    turn = await send(signed_in, session_id, "出一张商品主图")

    assert turn["status"] == "running"
    assert [step["tool"] for step in turn["steps"]] == ["generate_marketing"]
    assert turn["steps"][0]["label"] == "营销图"
    assert "营销图" in turn["reply"]


async def test_plain_answer_dispatches_nothing(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(AIMessage(content="现有工具做不到这个。"))
    session_id = (await open_session(signed_in))["id"]

    turn = await send(signed_in, session_id, "帮我写一首诗")

    assert turn["steps"] == []
    assert turn["reply"] == "现有工具做不到这个。"


async def test_long_refusal_keeps_only_the_first_sentence(
    signed_in: httpx.AsyncClient, fake_planner
):
    fake_planner(
        AIMessage(
            content="选区不一定包含老鼠。"
            "replace_region 需要完整提示词，adjust_image 也不能局部改色。"
        )
    )
    session_id = (await open_session(signed_in))["id"]

    turn = await send(signed_in, session_id, "老鼠换成红色")

    assert turn["steps"] == []
    assert turn["reply"] == "选区不一定包含老鼠。"
    assert "replace_region" not in turn["reply"]


def test_spoken_ignores_fallback_when_plan_exists():
    from app.agent.graph import _FALLBACK_REPLY, spoken

    assert "没太理解" not in spoken("", [{"tool": "flip_layer"}])
    assert spoken(_FALLBACK_REPLY, [{"tool": "flip_layer"}, {"tool": "rotate_layer"}]).startswith(
        "将按以下步骤执行"
    )


async def test_canvas_facts_are_given_to_the_planner(signed_in: httpx.AsyncClient, fake_planner):
    fake = fake_planner(AIMessage(content="好的。"))
    session_id = (await open_session(signed_in))["id"]

    await send(signed_in, session_id, "看看这张图")

    system = fake.messages[0].content
    assert "画幅 320×240" in system
    assert "修订号 1" in system
    assert "底图" in system
    assert "当前无选区" in system


async def test_existing_selection_is_given_to_the_planner(
    signed_in: httpx.AsyncClient, fake_planner
):
    fake = fake_planner(tool_call("replace_region", {"prompt": "改成黑色"}))
    session = await open_session(signed_in)
    selected = await signed_in.post(
        f"/api/sessions/{session['id']}/selection",
        json={"revision": session["revision"], "points": [{"x": 0.5, "y": 0.5}]},
    )
    assert selected.status_code == 200

    turn = await send(signed_in, session["id"], "骨头改成黑色")

    assert "已有选区" in fake.messages[0].content
    assert [step["tool"] for step in turn["steps"]] == ["replace_region"]


async def test_unregistered_tool_is_refused(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(tool_call("teleport_subject", {}))
    session_id = (await open_session(signed_in))["id"]

    turn = await send(signed_in, session_id, "把主体传送走")

    assert turn["steps"] == []
    assert "执行不了" in turn["reply"]


async def test_illegal_params_are_refused(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(tool_call("generate_image", {"prompt": "  ", "count": 99}))
    session_id = (await open_session(signed_in))["id"]

    turn = await send(signed_in, session_id, "随便来一张")

    assert turn["steps"] == []
    assert "执行不了" in turn["reply"]


async def test_results_join_the_wall_without_switching_current(
    signed_in: httpx.AsyncClient, fake_planner
):
    fake_planner(tool_call("generate_image", PROMPT))
    session = await open_session(signed_in)
    turn = await send(signed_in, session["id"], "换一张")

    await run_tool({}, uuid.UUID(turn["steps"][0]["run_id"]))

    updated = (await signed_in.get(f"/api/sessions/{session['id']}")).json()
    assert len(updated["assets"]) == 3
    assert updated["current_asset_id"] == session["current_asset_id"]
    assert updated["revision"] == 1

    turns = (await signed_in.get(f"/api/sessions/{session['id']}/messages")).json()
    assert turns[-1]["status"] == "succeeded"
    assert turns[-1]["steps"][0]["status"] == "succeeded"


async def test_conversation_is_returned_in_order(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(AIMessage(content="好的。"))
    session_id = (await open_session(signed_in))["id"]

    await send(signed_in, session_id, "第一句")
    await send(signed_in, session_id, "第二句")

    turns = (await signed_in.get(f"/api/sessions/{session_id}/messages")).json()
    assert [turn["goal"] for turn in turns] == ["第一句", "第二句"]


async def test_missing_api_key_fails_the_turn(signed_in: httpx.AsyncClient, monkeypatch):
    """模型不可用时必须明确失败，不能伪造成功结果。"""
    settings = get_settings()
    monkeypatch.setattr(settings, "dashscope_api_key", "")
    planner.cache_clear()
    session_id = (await open_session(signed_in))["id"]

    turn = await send(signed_in, session_id, "换个背景")

    planner.cache_clear()
    assert turn["status"] == "failed"
    assert "DASHSCOPE_API_KEY" in turn["error"]


async def test_blank_message_is_rejected(signed_in: httpx.AsyncClient):
    session_id = (await open_session(signed_in))["id"]

    response = await signed_in.post(f"/api/sessions/{session_id}/messages", json={"text": "   "})

    assert response.status_code == 422


async def test_messages_require_authentication(client: httpx.AsyncClient):
    path = f"/api/sessions/{uuid.uuid4()}/messages"

    assert (await client.get(path)).status_code == 401
    assert (await client.post(path, json={"text": "你好"})).status_code == 401


def test_cyclic_dependencies_are_rejected():
    from app.agent.plan import PlanError, assemble

    with pytest.raises(PlanError, match="循环"):
        assemble(
            [
                {"id": "a", "tool": "flip_layer", "params": {}, "depends_on": ["b"]},
                {"id": "b", "tool": "flip_layer", "params": {}, "depends_on": ["a"]},
            ]
        )


def test_plan_longer_than_limit_is_rejected():
    from app.agent.plan import MAX_STEPS, PlanError, assemble

    with pytest.raises(PlanError, match="超过"):
        assemble([{"tool": "flip_layer", "params": {}}] * (MAX_STEPS + 1))


async def test_multi_step_plan_waits_for_confirm(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(
        tool_calls(
            ("flip_layer", {"direction": "horizontal"}),
            ("rotate_layer", {"angle": 15}),
        )
    )
    session_id = (await open_session(signed_in))["id"]

    turn = await send(signed_in, session_id, "水平翻转再转 15 度")

    assert turn["status"] == "queued"
    assert "没太理解" not in turn["reply"]
    assert "确认后开始" in turn["reply"]
    assert [step["tool"] for step in turn["steps"]] == ["flip_layer", "rotate_layer"]
    assert turn["steps"][1]["depends_on"] == ["s1"]
    assert all(step["run_id"] is None for step in turn["steps"])

    session = (await signed_in.get(f"/api/sessions/{session_id}")).json()
    assert session["document"]["layers"][0]["transform"]["scale_x"] == 1


async def test_flip_steps_show_their_direction(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(
        tool_calls(
            ("flip_layer", {"direction": "horizontal"}),
            ("flip_layer", {"direction": "vertical"}),
        )
    )
    session_id = (await open_session(signed_in))["id"]

    turn = await send(signed_in, session_id, "水平翻转再垂直翻转")

    assert [step["label"] for step in turn["steps"]] == ["水平翻转", "垂直翻转"]
    assert "水平翻转、垂直翻转" in turn["reply"]


async def test_confirm_runs_dependent_steps_in_order(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(
        tool_calls(
            ("flip_layer", {"direction": "horizontal"}),
            ("rotate_layer", {"angle": 15}),
        )
    )
    session_id = (await open_session(signed_in))["id"]
    turn = await send(signed_in, session_id, "翻转并旋转")

    confirmed = (
        await signed_in.post(f"/api/sessions/{session_id}/messages/{turn['id']}/confirm")
    ).json()
    layer = (
        await signed_in.get(f"/api/sessions/{session_id}")
    ).json()["document"]["layers"][0]

    assert confirmed["status"] == "succeeded"
    assert [step["status"] for step in confirmed["steps"]] == ["succeeded", "succeeded"]
    assert layer["transform"]["scale_x"] == -1
    assert layer["transform"]["rotation"] == 15


async def test_queued_step_unblocks_the_next(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(
        tool_calls(
            ("remove_background", {}),
            ("flip_layer", {"direction": "horizontal"}),
        )
    )
    session = await open_session(signed_in)
    turn = await send(signed_in, session["id"], "去背景再水平翻转")
    started = (
        await signed_in.post(f"/api/sessions/{session['id']}/messages/{turn['id']}/confirm")
    ).json()

    assert started["status"] == "running"
    assert started["steps"][0]["run_id"]
    assert started["steps"][1]["run_id"] is None

    await run_tool({}, uuid.UUID(started["steps"][0]["run_id"]))
    finished = (await signed_in.get(f"/api/sessions/{session['id']}/messages")).json()[-1]
    updated = (await signed_in.get(f"/api/sessions/{session['id']}")).json()

    assert finished["status"] == "succeeded"
    assert [step["status"] for step in finished["steps"]] == ["succeeded", "succeeded"]
    assert updated["document"]["layers"][0]["transform"]["scale_x"] == -1


async def test_two_layers_in_one_turn_share_the_same_selection(
    signed_in: httpx.AsyncClient, fake_planner
):
    """选区被钉进每一步，第一步清除选区、修订号递增都不影响第二步。"""
    fake_planner(
        tool_calls(
            ("replace_region", {"prompt": "改成红色", "layer_id": "subject"}),
            ("replace_region", {"prompt": "改成蓝色", "layer_id": "background"}),
        )
    )
    session = await open_session(signed_in, image=scene())
    before = await apply(signed_in, session["id"], "split_layers")
    await select(signed_in, session["id"], before["revision"], points=[{"x": 0.5, "y": 0.5}])

    turn = await send(signed_in, session["id"], "主体改红色，背景改蓝色")
    await signed_in.post(f"/api/sessions/{session['id']}/messages/{turn['id']}/confirm")
    finished = await settle(signed_in, session["id"])
    after = (await signed_in.get(f"/api/sessions/{session['id']}")).json()

    assert finished["status"] == "succeeded"
    for layer_id in ("subject", "background"):
        assert layers(after)[layer_id]["asset_id"] != layers(before)[layer_id]["asset_id"]


async def test_selection_expires_when_the_plan_changes_the_canvas(
    signed_in: httpx.AsyncClient, fake_planner
):
    fake_planner(
        tool_calls(
            ("crop_canvas", {"ratio": "1:1"}),
            ("replace_region", {"prompt": "改成红色"}),
        )
    )
    session = await open_session(signed_in)
    await select(signed_in, session["id"], session["revision"], points=[{"x": 0.5, "y": 0.5}])

    turn = await send(signed_in, session["id"], "先裁成正方形再把选区改成红色")
    await signed_in.post(f"/api/sessions/{session['id']}/messages/{turn['id']}/confirm")
    finished = await settle(signed_in, session["id"])
    failed = next(step for step in finished["steps"] if step["tool"] == "replace_region")

    assert finished["status"] == "failed"
    assert "选区失效" in await error_of(signed_in, failed["run_id"])


async def test_cancel_drops_unstarted_steps(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(
        tool_calls(
            ("flip_layer", {"direction": "horizontal"}),
            ("rotate_layer", {"angle": 10}),
        )
    )
    session_id = (await open_session(signed_in))["id"]
    turn = await send(signed_in, session_id, "翻转再旋转")

    canceled = (
        await signed_in.post(f"/api/sessions/{session_id}/messages/{turn['id']}/cancel")
    ).json()
    session = (await signed_in.get(f"/api/sessions/{session_id}")).json()

    assert canceled["status"] == "canceled"
    assert [step["status"] for step in canceled["steps"]] == ["canceled", "canceled"]
    assert session["document"]["layers"][0]["transform"]["scale_x"] == 1


async def test_failed_step_can_be_retried(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(tool_call("replace_region", {"prompt": "改成黑色", "layer_id": "不存在的层"}))
    session_id = (await open_session(signed_in))["id"]
    turn = await send(signed_in, session_id, "把不存在的层换成黑色")

    await run_tool({}, uuid.UUID(turn["steps"][0]["run_id"]))
    failed = (await signed_in.get(f"/api/sessions/{session_id}/messages")).json()[-1]
    assert failed["status"] == "failed"

    retried = (
        await signed_in.post(f"/api/sessions/{session_id}/messages/{failed['id']}/retry")
    ).json()
    assert retried["status"] == "running"
    assert retried["steps"][0]["run_id"] != failed["steps"][0]["run_id"]
