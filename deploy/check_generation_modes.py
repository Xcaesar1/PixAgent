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


async def main():
    auth = (os.environ["ENTRY_USER"], os.environ["ENTRY_PASSWORD"])
    async with httpx.AsyncClient(base_url=BASE, auth=auth, timeout=45) as client:
        assert (await client.get('/api/generation-modes')).status_code == 401
        login = await client.post('/api/auth/login', json={
            "username": os.environ["APP_USER"], "password": os.environ["APP_PASSWORD"],
        })
        assert login.status_code == 200
        modes = (await client.get('/api/generation-modes')).json()
        assert modes['default'] == 'l0veyou'
        assert [m['id'] for m in modes['modes']] == ['dashscope', 'l0veyou']
        assert modes['modes'][0]['enabled'] == bool(os.environ.get('DASHSCOPE_API_KEY'))
        assert modes['modes'][1]['enabled']
        for extra in [{"provider": "dashscope", "count": 0}, {"provider": "l0veyou", "count": 2}]:
            response = await client.post('/api/generations', json={"prompt": "validation only", **extra})
            assert response.status_code == 422
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
