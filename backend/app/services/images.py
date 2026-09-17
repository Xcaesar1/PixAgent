import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 50_000_000
MIN_SIDE = 32

ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


class ImageRejected(Exception):
    pass


@dataclass(frozen=True)
class ImageMeta:
    image_format: str
    content_type: str
    extension: str
    width: int
    height: int
    size_bytes: int
    has_alpha: bool


def probe(data: bytes) -> ImageMeta:
    """校验图片并提取元信息。格式以实际解码结果为准，不采信文件扩展名。"""
    if not data:
        raise ImageRejected("文件为空")
    if len(data) > MAX_FILE_BYTES:
        raise ImageRejected(f"文件超过 {MAX_FILE_BYTES // 1024 // 1024} MB 上限")

    try:
        with Image.open(io.BytesIO(data)) as image:
            image_format = image.format or ""
            width, height = image.size
            has_alpha = image.mode in {"RGBA", "LA", "PA"} or "transparency" in image.info
            # 触发完整解码以暴露截断或损坏的数据
            image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ImageRejected("文件已损坏或不是受支持的图片") from exc

    if image_format not in ALLOWED_FORMATS:
        raise ImageRejected("仅支持 JPG、PNG 与 WebP")
    if min(width, height) < MIN_SIDE:
        raise ImageRejected(f"图片过小，最短边需不小于 {MIN_SIDE} 像素")
    if width * height > MAX_PIXELS:
        raise ImageRejected("图片像素总量过大")

    return ImageMeta(
        image_format=image_format,
        content_type=ALLOWED_FORMATS[image_format],
        extension=EXTENSIONS[image_format],
        width=width,
        height=height,
        size_bytes=len(data),
        has_alpha=has_alpha,
    )
