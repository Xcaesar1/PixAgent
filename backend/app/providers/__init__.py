from functools import lru_cache

from app.config import get_settings
from app.providers.base import EditRequest, GenerateRequest, ImageProvider, ProviderError
from app.providers.mock import MockImageProvider


@lru_cache
def get_image_provider() -> ImageProvider:
    """按配置选择实现。新增平台只需在此登记，调用方无需改动。"""
    name = get_settings().image_provider

    if name == "mock":
        return MockImageProvider()
    if name == "dashscope":
        from app.providers.dashscope import DashScopeImageProvider

        return DashScopeImageProvider()

    raise ProviderError(f"未知的 IMAGE_PROVIDER：{name}")


__all__ = [
    "EditRequest",
    "GenerateRequest",
    "ImageProvider",
    "ProviderError",
    "get_image_provider",
]
