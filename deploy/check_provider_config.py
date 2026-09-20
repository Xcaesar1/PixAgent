"""Read-only provider availability check; never submits a generation."""
import asyncio
import json
import os

import httpx


async def main():
    async with httpx.AsyncClient(
        base_url="https://pixagent.softk.ccwu.cc",
        auth=(os.environ["ENTRY_USER"], os.environ["ENTRY_PASSWORD"]),
        timeout=30,
    ) as client:
        assert (await client.get("/api/generation-modes")).status_code == 401
        login = await client.post("/api/auth/login", json={
            "username": os.environ["APP_USER"], "password": os.environ["APP_PASSWORD"],
        })
        assert login.status_code == 200
        modes = (await client.get("/api/generation-modes")).json()
        assert modes["default"] == "l0veyou"
        assert {m["id"]: m["enabled"] for m in modes["modes"]} == {
            "dashscope": True, "l0veyou": True,
        }
        health = (await client.get("/api/health")).json()
        assert all(value == "ok" for value in health.values())
        print(json.dumps({"domestic": "enabled", "gpt": "enabled", "default": "l0veyou",
                          "health": "pass", "new_generation_requests": 0}))


asyncio.run(main())
