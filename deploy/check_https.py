"""Verify public TLS, access controls and mock flow without exposing secrets."""
import asyncio
import io
import json
import os
from urllib.parse import urlsplit, urlunsplit

import httpx
from PIL import Image

BASE = "https://pixagent.softk.ccwu.cc"
S3 = "https://pixagent-s3.softk.ccwu.cc"


async def main():
    assert os.environ.get("IMAGE_PROVIDER") == "mock", "Paid providers are not authorized"
    auth = (os.environ["ENTRY_USER"], os.environ["ENTRY_PASSWORD"])
    credentials = {"username": os.environ["APP_USER"], "password": os.environ["APP_PASSWORD"]}
    async with httpx.AsyncClient(timeout=90, trust_env=False) as anon:
        assert (await anon.get(BASE + "/auth")).status_code == 401
        assert (await anon.get(BASE + "/api/health", auth=(auth[0], "invalid"))).status_code == 401
        assert (await anon.get(S3 + "/")).status_code == 403
        assert (await anon.get(S3 + "/minio/")).status_code == 403
        assert (await anon.put(S3 + "/pixagent/users/blocked.png", content=b"blocked")).status_code == 403
        redirect = await anon.get(BASE.replace("https:", "http:") + "/auth")
        assert redirect.status_code == 308
        async with httpx.AsyncClient(base_url=BASE, auth=auth, timeout=90, trust_env=False) as client:
            assert (await client.get("/auth")).status_code == 200
            assert (await client.get("/api/assets")).status_code == 401
            health = (await client.get("/api/health")).json()
            assert all(v == "ok" for v in health.values())
            assert (await client.post("/api/auth/register", json=credentials)).status_code == 403
            response = await client.post("/api/auth/login", json=credentials)
            assert response.status_code == 200
            cookie = response.headers["set-cookie"].lower()
            assert "secure" in cookie and "httponly" in cookie and "samesite=lax" in cookie
            buffer = io.BytesIO()
            Image.new("RGB", (128, 128), "orange").save(buffer, "PNG")
            response = await client.post("/api/assets", files={"file": ("https-check.png", buffer.getvalue(), "image/png")})
            assert response.status_code == 201
            image_url = response.json()["url"]
            assert image_url.startswith(S3 + "/pixagent/users/")
            image = await anon.get(image_url, headers={"Origin": BASE})
            assert image.status_code == 200
            assert image.headers["access-control-allow-origin"] == BASE
            parts = urlsplit(image_url)
            unsigned = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
            assert (await anon.get(unsigned)).status_code == 403
            response = await client.post("/api/generations", json={"provider": "mock", "prompt": "HTTPS mock acceptance", "count": 1, "ratio": "1:1"})
            assert response.status_code == 202
            run_id = response.json()["id"]
            frames = []
            async with client.stream("GET", f"/events/runs/{run_id}") as stream:
                assert stream.status_code == 200
                async for line in stream.aiter_lines():
                    if line.startswith("data: "):
                        frames.append(json.loads(line[6:]))
                        if frames[-1]["status"] in ("succeeded", "failed", "canceled"):
                            break
            assert frames[-1]["status"] == "succeeded"
            run = (await client.get(f"/api/runs/{run_id}")).json()
            assert (await anon.get(run["candidates"][0]["url"])).status_code == 200
            print(json.dumps({"tls": "verified", "entry_auth": "pass", "secure_cookie": "pass", "registration_closed": "pass", "upload": "pass", "signed_images_cors": "pass", "unsigned_images_denied": "pass", "storage_management_denied": "pass", "mock_worker": "pass", "sse_frames": len(frames)}))


asyncio.run(main())
