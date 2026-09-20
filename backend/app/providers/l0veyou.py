import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx

from app.config import get_settings
from app.providers.base import GenerateRequest, ProgressCallback, ProviderError
from app.providers.generation_modes import GPT_RATIOS
from app.services.images import MAX_FILE_BYTES

BASE_URL = "https://l0veyou.com"
POLL_TIMEOUT = 180.0
POLL_INTERVAL = 3.0
# 2026-09-20 实测：站点原图改由 cdn.ng-resource.com 提供，旧 CloudFront 域名继续保留兼容。
IMAGE_HOST = "cdn.ng-resource.com"
IMAGE_HOSTS = (IMAGE_HOST, "d1ptb5b3fy36g3.cloudfront.net")


class L0veyouImageProvider:
    name = "l0veyou"

    def __init__(self, model: str = "gpt-image-2") -> None:
        # 上游模型由服务端按模式固定注入，浏览器无法指定。
        self.model = model

    async def generate(
        self,
        request: GenerateRequest,
        on_progress: ProgressCallback | None = None,
        *,
        task_id: str | None = None,
        on_submitted: Callable[[str], Awaitable[None]] | None = None,
    ) -> list[bytes]:
        ratio = next(
            (
                r
                for r in GPT_RATIOS
                if request.width * int(r.split(":")[1]) == request.height * int(r.split(":")[0])
            ),
            None,
        )
        if request.count != 1 or ratio is None or request.references or request.seed is not None:
            raise ProviderError("GPT 模式仅支持单张文生图和已列出的比例")
        try:
            token = Path(get_settings().l0veyou_token_file).read_text().strip()
        except OSError:
            raise ProviderError("GPT 登录凭证不可用，请联系管理员") from None
        if not token:
            raise ProviderError("GPT 登录凭证不可用，请联系管理员")
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Origin": BASE_URL,
            "Referer": BASE_URL + "/chat",
        }
        try:
            async with httpx.AsyncClient(base_url=BASE_URL, headers=headers, timeout=30) as client:
                if not task_id:
                    prompt = request.prompt
                    if request.negative_prompt:
                        prompt += "\nAvoid: " + request.negative_prompt
                    # Never retry submission: a lost response may still mean a created task.
                    body = self._parse(
                        await client.post(
                            "/api/v1/images/generate",
                            json={
                                "model": self.model,
                                "prompt": prompt,
                                "aspect_ratio": ratio,
                            },
                        )
                    )
                    task_id = body.get("id")
                    if not isinstance(task_id, str) or not task_id:
                        raise ProviderError("GPT 服务未返回任务编号，未自动重试")
                    if on_submitted:
                        await on_submitted(task_id)
                deadline = asyncio.get_running_loop().time() + POLL_TIMEOUT
                while True:
                    body = self._parse(
                        await client.get("/api/v1/images/tasks/" + quote(task_id, safe=""))
                    )
                    status = body.get("status")
                    if status == "completed":
                        urls = body.get("image_urls") or []
                        originals = [
                            url
                            for url in urls
                            if isinstance(url, str)
                            and "thumbnail" not in urlsplit(url).path.lower()
                        ]
                        if not originals:
                            raise ProviderError("GPT 任务完成但未返回原图")
                        return [await self._download(originals[0])]
                    if status in {"failed", "canceled", "cancelled"}:
                        raise ProviderError("GPT 生图任务失败，请检查站点账号额度后再试")
                    if asyncio.get_running_loop().time() >= deadline:
                        raise ProviderError("GPT 生图等待超时，未重复提交，请稍后查看站点任务")
                    if on_progress:
                        await on_progress(45, "GPT 生图中")
                    await asyncio.sleep(POLL_INTERVAL)
        except httpx.RequestError:
            raise ProviderError("GPT 服务连接失败，未自动重新提交，请稍后检查任务") from None

    @staticmethod
    def _parse(response: httpx.Response) -> dict:
        if response.status_code == 401:
            raise ProviderError("GPT 登录已过期，请联系管理员更新登录凭证")
        if response.status_code == 403:
            raise ProviderError("GPT 服务拒绝访问，请联系管理员检查账号和服务器访问状态")
        if response.status_code == 429:
            raise ProviderError("GPT 请求过于频繁或额度不足，请稍后再试")
        if response.status_code != 200:
            raise ProviderError(f"GPT 服务暂不可用（HTTP {response.status_code}）")
        try:
            body = response.json()
            if isinstance(body, dict) and isinstance(body.get("data"), dict):
                body = body["data"]
            if not isinstance(body, dict):
                raise ValueError
            return body
        except ValueError:
            raise ProviderError("GPT 服务返回异常响应") from None

    @staticmethod
    async def _download(url: str) -> bytes:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in IMAGE_HOSTS
            or parsed.port not in (None, 443)
        ):
            raise ProviderError("GPT 返回了未支持的图片地址，请联系管理员")
        # Use a separate client so the account credential never reaches the image CDN.
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("GET", url) as response:
                if response.status_code != 200:
                    raise ProviderError("GPT 原图下载失败")
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_FILE_BYTES:
                        raise ProviderError("GPT 原图超过 20 MB 上限")
        return bytes(data)
