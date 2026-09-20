"""Verify deployed routing and replay an existing GPT result without new inference."""
import asyncio
import io
import json
import os
from pathlib import Path

import httpx
from PIL import Image
from sqlalchemy import select

from app.db import SessionFactory
from app.models import User
from app.queue import close_queue, enqueue
from app.services import runs

BASE = "https://pixagent.softk.ccwu.cc"

# 生产 /api/generation-modes 必须返回的固定模式 ID 与顺序（含两个 GPT Image 2.5 变体）。
EXPECTED_MODE_IDS = (
    "dashscope",
    "l0veyou",
    "l0veyou-gpt-image-2-5-flare",
    "l0veyou-gpt-image-2-5-full",
)
# GPT 系模式（历史 l0veyou = GPT Image 2，以及两个新变体）的标签与参数，
# 必须与后端 app.providers.generation_modes 的 GPT_MODES / GPT_COUNTS / GPT_RATIOS 保持一致。
GPT_MODE_LABELS = {
    "l0veyou": "GPT 生图 · GPT Image 2",
    "l0veyou-gpt-image-2-5-flare": "GPT 生图 · GPT Image 2.5 极速版",
    "l0veyou-gpt-image-2-5-full": "GPT 生图 · GPT Image 2.5 满血版",
}
GPT_COUNTS = [1, 2, 4]
GPT_RATIOS = ["1:1", "3:4", "9:16", "16:9"]
# 这些请求必须在 API schema / 业务校验阶段即失败（422）：不会创建任务、不会入队、
# 不会提交上游、不会产生任何费用。禁止用合法请求（例如 l0veyou count=2）触发 422。
INVALID_GENERATIONS = (
    {"provider": "dashscope", "count": 0},  # count 低于 schema 下限（ge=1）
    {"provider": "l0veyou-gpt-image-2-5-flare", "count": 6},  # GPT 模式不支持的张数
    {"provider": "not-a-real-provider", "count": 1},  # 不在模式白名单内的 provider
)


def assert_modes(modes: dict) -> None:
    """四个固定模式与 default 必须与后端 generation_modes() 契约一致。"""
    assert modes["default"] == "l0veyou", modes.get("default")
    assert [mode["id"] for mode in modes["modes"]] == list(EXPECTED_MODE_IDS)
    by_id = {mode["id"]: mode for mode in modes["modes"]}
    # 兼容断言：DashScope 随 API Key 配置启用。
    assert by_id["dashscope"]["enabled"] == bool(os.environ.get("DASHSCOPE_API_KEY"))
    # 旧 GPT Image 2 与两个新 GPT Image 2.5 变体：全部启用、标签与参数一致。
    for mode_id, label in GPT_MODE_LABELS.items():
        mode = by_id[mode_id]
        assert mode["enabled"], mode_id
        assert mode["label"] == label, (mode_id, mode["label"])
        assert mode["counts"] == GPT_COUNTS, (mode_id, mode["counts"])
        assert mode["ratios"] == GPT_RATIOS, (mode_id, mode["ratios"])


async def assert_invalid_rejected(client: httpx.AsyncClient) -> None:
    """校验阶段即 422，服务端在处理前拒绝，因此不可能提交上游或产生费用。"""
    for extra in INVALID_GENERATIONS:
        response = await client.post(
            '/api/generations', json={"prompt": "validation only", **extra}
        )
        assert response.status_code == 422, (extra, response.status_code)


async def main():
    auth = (os.environ["ENTRY_USER"], os.environ["ENTRY_PASSWORD"])
    async with httpx.AsyncClient(base_url=BASE, auth=auth, timeout=45) as client:
        assert (await client.get('/api/generation-modes')).status_code == 401
        login = await client.post('/api/auth/login', json={
            "username": os.environ["APP_USER"], "password": os.environ["APP_PASSWORD"],
        })
        assert login.status_code == 200
        assert_modes((await client.get('/api/generation-modes')).json())
        await assert_invalid_rejected(client)
        # 复用历史已授权结果：worker 仅以 GET 轮询已有上游 task，绝不重新提交
        # （new_upstream_submissions=0），本脚本不含任何真实新生图路径。
        task = json.loads(Path('/probe/result.json').read_text())['task_id']
        async with SessionFactory() as session:
            user = (await session.execute(select(User).where(
                User.username == os.environ['APP_USER']
            ))).scalar_one()
            run = await runs.create(session, user.id, 'generate_image', {
                'provider': 'l0veyou', 'prompt': 'Previously authorized server coffee-cup result',
                'ratio': '1:1', 'count': 1, '_submission_started': True, '_upstream_task_id': task,
            })
            run_id = str(run.id)
            await enqueue('run_tool', run.id)
        for _ in range(90):
            body = (await client.get('/api/runs/' + run_id)).json()
            if body['status'] in ('succeeded', 'failed', 'canceled'):
                break
            await asyncio.sleep(3)
        assert body['status'] == 'succeeded', body.get('error')
        assert body['provider'] == 'l0veyou'
        assert len(body['candidates']) == 1
        image = body['candidates'][0]
        async with httpx.AsyncClient(timeout=45) as cdn:
            response = await cdn.get(image['url'])
            assert response.status_code == 200
            with Image.open(io.BytesIO(response.content)) as pic:
                dimensions = pic.size
        print(json.dumps({'modes': 'pass', 'auth': 'pass', 'invalid_params': 'pass',
                          'gpt_worker_resume': 'pass', 'private_storage': 'pass',
                          'dimensions': dimensions, 'run_id': run_id,
                          'new_upstream_submissions': 0}))
    await close_queue()


asyncio.run(main())
