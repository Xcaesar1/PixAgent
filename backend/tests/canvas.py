"""画布测试辅助：下发工具、建选区、构造场景图、按 id 取图层。"""

import uuid
from io import BytesIO

import httpx
from PIL import Image, ImageDraw

from app.tasks.tools import run_tool

_QUEUED = {"queued", "running"}


async def invoke(
    client: httpx.AsyncClient, session_id: str, tool: str, params: dict | None = None
) -> dict:
    response = await client.post(
        f"/api/sessions/{session_id}/tools", json={"tool": tool, "params": params or {}}
    )
    assert response.status_code == 202, response.text
    return response.json()


async def apply(
    client: httpx.AsyncClient, session_id: str, tool: str, params: dict | None = None
) -> dict:
    """下发并跑完一个排队工具，返回执行后的会话。"""
    body = await invoke(client, session_id, tool, params)
    await run_tool({}, uuid.UUID(body["run"]["id"]))
    return (await client.get(f"/api/sessions/{session_id}")).json()


async def select(client: httpx.AsyncClient, session_id: str, revision: int, **payload) -> dict:
    response = await client.post(
        f"/api/sessions/{session_id}/selection", json={"revision": revision, **payload}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def settle(client: httpx.AsyncClient, session_id: str) -> dict:
    """依次跑完最后一轮里排队的步骤，每步结束后重新取计划再看下一步。"""
    while True:
        turn = (await client.get(f"/api/sessions/{session_id}/messages")).json()[-1]
        pending = next(
            (step for step in turn["steps"] if step["run_id"] and step["status"] in _QUEUED),
            None,
        )
        if pending is None:
            return turn
        await run_tool({}, uuid.UUID(pending["run_id"]))


async def error_of(client: httpx.AsyncClient, run_id: str) -> str:
    return (await client.get(f"/api/runs/{run_id}")).json()["error"] or ""


def scene(size: tuple[int, int] = (320, 240)) -> bytes:
    """浅底 + 居中蓝色椭圆，抠图与点选都能稳定命中中心。"""
    image = Image.new("RGB", size, (230, 220, 200))
    ImageDraw.Draw(image).ellipse((80, 40, 240, 200), fill=(30, 90, 180))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def layers(session: dict) -> dict[str, dict]:
    return {layer["id"]: layer for layer in session["document"]["layers"]}
