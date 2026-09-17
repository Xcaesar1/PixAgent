from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol

ProgressCallback = Callable[[int, str], Awaitable[None]]


class ProviderError(Exception):
    """模型服务不可用或返回失败。"""


@dataclass(frozen=True)
class GenerateRequest:
    prompt: str
    width: int
    height: int
    count: int = 1
    negative_prompt: str | None = None
    seed: int | None = None
    # 参考图以原始字节传入，由各 adapter 决定编码方式
    references: list[bytes] = field(default_factory=list)


@dataclass(frozen=True)
class EditRequest:
    prompt: str
    image: bytes
    count: int = 1
    width: int | None = None
    height: int | None = None
    negative_prompt: str | None = None


class ImageProvider(Protocol):
    name: str

    async def generate(
        self, request: GenerateRequest, on_progress: ProgressCallback | None = None
    ) -> list[bytes]:
        """返回 count 张图片的原始字节。失败时抛出 ProviderError。"""
        ...

    async def edit(
        self, request: EditRequest, on_progress: ProgressCallback | None = None
    ) -> list[bytes]:
        """按提示词改已有图片。width/height 有值时同时改画幅，用于扩图。"""
        ...

    async def upscale(
        self, image: bytes, scale: int, on_progress: ProgressCallback | None = None
    ) -> bytes:
        """提高分辨率，不改变构图。"""
        ...
