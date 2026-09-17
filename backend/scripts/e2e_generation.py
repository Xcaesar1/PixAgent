"""文生图链路端到端验证：登录、发起生成、订阅进度、读取候选图、校验签名 URL。"""

import asyncio
import json
import sys

import httpx

BASE = "http://127.0.0.1:7302"
USER = {"username": "s3tester", "password": "s3pass123"}


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0, trust_env=False) as client:
        response = await client.post("/api/auth/register", json=USER)
        if response.status_code == httpx.codes.CONFLICT:
            response = await client.post("/api/auth/login", json=USER)
        assert response.status_code in (200, 201), response.text
        print(f"[1] 登录成功 {response.json()['username']}")

        response = await client.post(
            "/api/generations",
            json={"prompt": "一只在草地上的橘猫，柔和阳光", "ratio": "4:5", "count": 4},
        )
        assert response.status_code == httpx.codes.ACCEPTED, response.text
        run_id = response.json()["id"]
        print(f"[2] 任务已入队 status={response.json()['status']} id={run_id}")

        frames = []
        async with client.stream("GET", f"/events/runs/{run_id}", timeout=90.0) as stream:
            assert stream.status_code == httpx.codes.OK, stream.status_code
            async for line in stream.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = json.loads(line[6:])
                frames.append(payload)
                print(
                    f"    SSE {payload['status']:<10} {payload['progress']:>3}% {payload['stage']}"
                )
                if payload["status"] in ("succeeded", "failed", "canceled"):
                    break

        assert frames, "未收到任何 SSE 帧"
        assert frames[-1]["status"] == "succeeded", frames[-1]
        print(f"[3] SSE 收到 {len(frames)} 帧，终态 succeeded")

        response = await client.get(f"/api/runs/{run_id}")
        assert response.status_code == httpx.codes.OK, response.text
        candidates = response.json()["candidates"]
        assert len(candidates) == 4, f"候选图数量应为 4，实际 {len(candidates)}"
        sizes = {(c["width"], c["height"]) for c in candidates}
        assert sizes == {(1080, 1350)}, sizes
        print(f"[4] 候选图 4 张，尺寸 {sizes.pop()} 符合 4:5")

        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as anon:
            image = await anon.get(candidates[0]["url"])
        assert image.status_code == httpx.codes.OK, image.status_code
        assert image.content[:8] == b"\x89PNG\r\n\x1a\n", "签名 URL 未返回 PNG"
        print(f"[5] 签名 URL 可下载，PNG {len(image.content)} 字节")

        response = await client.post(
            "/api/generations", json={"prompt": "   ", "ratio": "1:1", "count": 4}
        )
        assert response.status_code == httpx.codes.UNPROCESSABLE_ENTITY, response.status_code
        print("[6] 空提示词被拒绝")

        async with httpx.AsyncClient(base_url=BASE, timeout=10.0, trust_env=False) as anon:
            response = await anon.get(f"/api/runs/{run_id}")
        assert response.status_code == httpx.codes.UNAUTHORIZED, response.status_code
        print("[7] 未登录访问任务被拒绝")

    print("\n全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
