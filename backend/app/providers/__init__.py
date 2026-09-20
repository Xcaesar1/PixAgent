from functools import lru_cache

from app.config import get_settings
from app.providers.base import EditRequest, GenerateRequest, ImageProvider, ProviderError
from app.providers.generation_modes import gpt_model_of
from app.providers.mock import MockImageProvider


@lru_cache
def get_image_provider(name: str | None = None) -> ImageProvider:
    """按配置选择实现。新增平台只需在此登记，调用方无需改动。"""
    name = name or get_settings().image_provider

    if name == "mock":
        return MockImageProvider()
    if name == "dashscope":
        from app.providers.dashscope import DashScopeImageProvider

        return DashScopeImageProvider()

    # 每个 GPT 模式复用同一个适配器，只固定各自的上游模型标识。
    model = gpt_model_of(name)
    if model:
        from app.providers.l0veyou import L0veyouImageProvider

        return L0veyouImageProvider(model=model)

    raise ProviderError(f"未知的 IMAGE_PROVIDER：{name}")


__all__ = [
    "EditRequest",
    "GenerateRequest",
    "ImageProvider",
    "ProviderError",
    "get_image_provider",
]
