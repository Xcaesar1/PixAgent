import asyncio
import colorsys
import hashlib
import io

from PIL import Image, ImageDraw

from app.providers.base import EditRequest, GenerateRequest, ImageProvider, ProgressCallback

_STEP_DELAY = 0.4


class MockImageProvider(ImageProvider):
    """本地占位图实现，不产生真实调用费用。构图由提示词哈希决定，同一提示词结果稳定。"""

    name = "mock"

    async def generate(
        self, request: GenerateRequest, on_progress: ProgressCallback | None = None
    ) -> list[bytes]:
        images: list[bytes] = []
        seed = int(hashlib.sha256(request.prompt.encode()).hexdigest()[:8], 16)

        for index in range(request.count):
            await asyncio.sleep(_STEP_DELAY)
            if on_progress:
                progress = int((index + 1) / request.count * 100)
                await on_progress(progress, f"生成第 {index + 1} / {request.count} 张")
            images.append(self._render(request, seed + index * 977, index))

        return images

    async def edit(
        self, request: EditRequest, on_progress: ProgressCallback | None = None
    ) -> list[bytes]:
        source = Image.open(io.BytesIO(request.image)).convert("RGBA")
        width = request.width or source.width
        height = request.height or source.height
        seed = int(hashlib.sha256(request.prompt.encode()).hexdigest()[:8], 16)
        images: list[bytes] = []

        for index in range(request.count):
            await asyncio.sleep(_STEP_DELAY)
            if on_progress:
                await on_progress(
                    int((index + 1) / request.count * 100),
                    f"生成第 {index + 1} / {request.count} 张",
                )
            images.append(self._compose(source, width, height, seed + index * 977, request.prompt))

        return images

    async def upscale(
        self, image: bytes, scale: int, on_progress: ProgressCallback | None = None
    ) -> bytes:
        source = Image.open(io.BytesIO(image)).convert("RGBA")
        if on_progress:
            await on_progress(40, "放大画幅")
        await asyncio.sleep(_STEP_DELAY)
        enlarged = source.resize(
            (source.width * scale, source.height * scale), Image.Resampling.LANCZOS
        )
        if on_progress:
            await on_progress(90, "保存结果")
        return _png(enlarged)

    def _compose(
        self, source: Image.Image, width: int, height: int, seed: int, prompt: str
    ) -> bytes:
        hue = (seed % 360) / 360
        fill = tuple(int(channel * 255) for channel in colorsys.hls_to_rgb(hue, 0.82, 0.38))
        canvas = Image.new("RGBA", (width, height), (*fill, 255))
        # 同尺寸当作换背景，略缩小主体露出新底；扩图则原大居中
        scale = 0.88 if (width, height) == source.size else 1
        size = (
            max(1, int(source.width * scale)),
            max(1, int(source.height * scale)),
        )
        placed = source.resize(size, Image.Resampling.LANCZOS)
        canvas.paste(placed, ((width - size[0]) // 2, (height - size[1]) // 2), placed)
        ImageDraw.Draw(canvas).text((16, 16), prompt[:40], fill=(255, 255, 255))
        return _png(canvas)

    def _render(self, request: GenerateRequest, seed: int, index: int) -> bytes:
        hue = (seed % 360) / 360
        base = tuple(int(c * 255) for c in colorsys.hls_to_rgb(hue, 0.82, 0.38))
        accent = tuple(int(c * 255) for c in colorsys.hls_to_rgb((hue + 0.5) % 1, 0.45, 0.5))

        image = Image.new("RGB", (request.width, request.height), base)
        draw = ImageDraw.Draw(image)

        short = min(request.width, request.height)
        cx, cy = request.width // 2, request.height // 2
        radius = short // 3 + (index % 3) * short // 24
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=accent)
        draw.text((16, 16), f"{request.prompt[:40]}\n#{index + 1}", fill=(255, 255, 255))

        return _png(image)


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
