import asyncio
import base64
import io

import httpx
from PIL import Image

from app.config import get_settings
from app.providers.base import (
    EditRequest,
    GenerateRequest,
    ImageProvider,
    ProgressCallback,
    ProviderError,
)

_SUBMIT_PATH = "/api/v1/services/aigc/image-generation/generation"
_EDIT_PATH = "/api/v1/services/aigc/multimodal-generation/generation"
_TASK_PATH = "/api/v1/tasks/{task_id}"
_MAX_EDGE = 2048
_MIN_EDGE = 512
_EDIT_TIMEOUT = 180.0

_POLL_INTERVAL = 3.0
_POLL_TIMEOUT = 300.0
_TERMINAL = {"SUCCEEDED", "FAILED", "CANCELED", "UNKNOWN"}

_PENDING = (10, "排队中")


class DashScopeImageProvider(ImageProvider):
    """百炼千问图像模型。

    文生图走异步任务（X-DashScope-Async + 轮询）。
    图像编辑接口不支持异步，必须同步等待结果。
    """

    name = "dashscope"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.dashscope_api_key:
            raise ProviderError("未配置 DASHSCOPE_API_KEY")
        self._model = settings.text_to_image_model
        self._edit_model = settings.image_edit_model
        self._client = httpx.AsyncClient(
            base_url=settings.dashscope_base_url,
            headers={"Authorization": f"Bearer {settings.dashscope_api_key}"},
            timeout=30.0,
        )

    async def generate(
        self, request: GenerateRequest, on_progress: ProgressCallback | None = None
    ) -> list[bytes]:
        task_id = await self._submit(_SUBMIT_PATH, self._payload(request))
        urls = await self._await_result(task_id, on_progress)
        return await asyncio.gather(*(self._download(url) for url in urls))

    async def edit(
        self, request: EditRequest, on_progress: ProgressCallback | None = None
    ) -> list[bytes]:
        if on_progress:
            await on_progress(20, "提交编辑")
        response = await self._client.post(
            _EDIT_PATH,
            json=self._edit_payload(request),
            timeout=_EDIT_TIMEOUT,
        )
        urls = _extract_urls(self._parse(response).get("output", {}))
        if on_progress:
            await on_progress(80, "下载结果")
        return await asyncio.gather(*(self._download(url) for url in urls))

    async def upscale(
        self, image: bytes, scale: int, on_progress: ProgressCallback | None = None
    ) -> bytes:
        source = Image.open(io.BytesIO(image))
        width, height = _scaled_size(source.width, source.height, scale)
        results = await self.edit(
            EditRequest(
                prompt="提高清晰度，保持主体、构图和颜色不变，不要添加新元素。",
                image=image,
                width=width,
                height=height,
            ),
            on_progress,
        )
        return results[0]

    def _payload(self, request: GenerateRequest) -> dict:
        # 本地对象存储无法被模型服务访问，参考图一律以 base64 内联
        content: list[dict] = [
            {"image": f"data:image/png;base64,{base64.b64encode(raw).decode()}"}
            for raw in request.references
        ]
        content.append({"text": request.prompt})

        parameters: dict = {
            "n": request.count,
            "size": f"{request.width}*{request.height}",
            "watermark": False,
        }
        if request.negative_prompt:
            parameters["negative_prompt"] = request.negative_prompt
        if request.seed is not None:
            parameters["seed"] = request.seed

        return {
            "model": self._model,
            "input": {"messages": [{"role": "user", "content": content}]},
            "parameters": parameters,
        }

    def _edit_payload(self, request: EditRequest) -> dict:
        content = [
            {"image": f"data:image/png;base64,{base64.b64encode(request.image).decode()}"},
            {"text": request.prompt},
        ]
        parameters: dict = {"n": request.count, "watermark": False}
        if request.width and request.height:
            width, height = _fit_edit_size(request.width, request.height)
            parameters["size"] = f"{width}*{height}"
        if request.negative_prompt:
            parameters["negative_prompt"] = request.negative_prompt
        return {
            "model": self._edit_model,
            "input": {"messages": [{"role": "user", "content": content}]},
            "parameters": parameters,
        }

    async def _submit(self, path: str, payload: dict) -> str:
        response = await self._client.post(
            path,
            json=payload,
            headers={"X-DashScope-Async": "enable"},
        )
        body = self._parse(response)
        task_id = body.get("output", {}).get("task_id")
        if not task_id:
            raise ProviderError("模型服务未返回任务 ID")
        return task_id

    async def _await_result(self, task_id: str, on_progress: ProgressCallback | None) -> list[str]:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _POLL_TIMEOUT
        started = loop.time()

        while True:
            response = await self._client.get(_TASK_PATH.format(task_id=task_id))
            output = self._parse(response).get("output", {})
            status = output.get("task_status", "UNKNOWN")

            if status in _TERMINAL:
                if status != "SUCCEEDED":
                    raise ProviderError(f"生成任务{status}：{output.get('message', '未知原因')}")
                return _extract_urls(output)

            if on_progress:
                if status == "PENDING":
                    await on_progress(*_PENDING)
                elif status == "RUNNING":
                    waited = loop.time() - started
                    await on_progress(min(82, 38 + int(waited / 2.2)), "生成中")

            if loop.time() > deadline:
                raise ProviderError("生成任务超时")
            await asyncio.sleep(_POLL_INTERVAL)

    async def _download(self, url: str) -> bytes:
        """结果 URL 有效期 24 小时，须立即取回并转存到自有存储。"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url)
        if response.status_code != httpx.codes.OK:
            raise ProviderError("生成结果下载失败")
        return response.content

    @staticmethod
    def _parse(response: httpx.Response) -> dict:
        try:
            body = response.json()
        except ValueError as exc:
            raise ProviderError(f"模型服务返回非 JSON 响应（HTTP {response.status_code}）") from exc

        if response.status_code != httpx.codes.OK or "code" in body:
            raise ProviderError(body.get("message") or f"模型服务错误 HTTP {response.status_code}")
        return body


def _extract_urls(output: dict) -> list[str]:
    urls = [
        item["image"]
        for choice in output.get("choices", [])
        for item in choice.get("message", {}).get("content", [])
        if "image" in item
    ]
    if not urls:
        raise ProviderError("生成任务成功但未返回图片")
    return urls


def _scaled_size(width: int, height: int, scale: int) -> tuple[int, int]:
    return _fit_edit_size(width * scale, height * scale)


def _fit_edit_size(width: int, height: int) -> tuple[int, int]:
    """编辑接口边长必须在 [512, 2048]。"""
    scale = max(_MIN_EDGE / min(width, height), 1)
    width, height = int(width * scale), int(height * scale)
    long_edge = max(width, height)
    if long_edge > _MAX_EDGE:
        factor = _MAX_EDGE / long_edge
        width, height = int(width * factor), int(height * factor)
    return max(_MIN_EDGE, width), max(_MIN_EDGE, height)
