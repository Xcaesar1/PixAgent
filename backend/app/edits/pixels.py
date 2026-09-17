import io
import math

from PIL import Image, ImageChops, ImageEnhance, ImageFilter

_CORNER_TOLERANCE = 28


def remove_background(data: bytes) -> bytes:
    """auto 模式下优先 rembg；corner 仅用四角颜色，避免测试下载模型。"""
    from app.config import get_settings

    provider = get_settings().matting_provider
    if provider != "corner":
        try:
            from rembg import remove
        except ImportError:
            if provider == "rembg":
                raise
        else:
            return bytes(remove(data))
    return _corner_matte(data)


def adjust(
    data: bytes,
    *,
    brightness: float = 0,
    contrast: float = 0,
    highlights: float = 0,
    shadows: float = 0,
    temperature: float = 0,
    tint: float = 0,
    saturation: float = 0,
    vibrance: float = 0,
    sharpness: float = 0,
    clarity: float = 0,
    vignette: float = 0,
) -> bytes:
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    red, green, blue, alpha = image.split()
    rgb = Image.merge("RGB", (red, green, blue))

    if brightness:
        rgb = ImageEnhance.Brightness(rgb).enhance(1 + brightness)
    if contrast:
        rgb = ImageEnhance.Contrast(rgb).enhance(1 + contrast)
    if saturation:
        rgb = ImageEnhance.Color(rgb).enhance(1 + saturation)
    if sharpness:
        rgb = ImageEnhance.Sharpness(rgb).enhance(1 + sharpness)
    if highlights or shadows:
        rgb = _tone(rgb, highlights, shadows)
    if temperature or tint:
        rgb = _white_balance(rgb, temperature, tint)
    if vibrance:
        rgb = _vibrance(rgb, vibrance)
    if clarity:
        rgb = rgb.filter(ImageFilter.UnsharpMask(radius=2, percent=int(80 * clarity), threshold=2))
    if vignette:
        rgb = ImageChops.multiply(rgb, _vignette_mask(rgb.size, vignette))

    image = rgb.convert("RGBA")
    image.putalpha(alpha)
    return _png(image)


def _tone(image: Image.Image, highlights: float, shadows: float) -> Image.Image:
    def curve(value: int) -> int:
        unit = value / 255
        value += shadows * (1 - unit) * 64
        value += highlights * unit * 64
        return max(0, min(255, int(value)))

    return image.point(curve)


def _white_balance(image: Image.Image, temperature: float, tint: float) -> Image.Image:
    r, g, b = image.split()
    r = r.point(lambda value: _clip(value + temperature * 28 + tint * 12))
    g = g.point(lambda value: _clip(value - tint * 20))
    b = b.point(lambda value: _clip(value - temperature * 28 + tint * 12))
    return Image.merge("RGB", (r, g, b))


def _vibrance(image: Image.Image, amount: float) -> Image.Image:
    """少饱和的像素多加一点，避免已鲜艳的颜色过曝。"""
    pixels = image.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            red, green, blue = pixels[x, y]
            average = (red + green + blue) / 3
            chroma = (abs(red - average) + abs(green - average) + abs(blue - average)) / 3
            weight = amount * (1 - chroma / 128)
            pixels[x, y] = (
                _clip(red + (red - average) * weight),
                _clip(green + (green - average) * weight),
                _clip(blue + (blue - average) * weight),
            )
    return image


def _vignette_mask(size: tuple[int, int], amount: float) -> Image.Image:
    overlay = Image.new("RGB", size)
    pixels = overlay.load()
    cx, cy = size[0] / 2, size[1] / 2
    farthest = math.hypot(cx, cy) or 1
    for y in range(size[1]):
        for x in range(size[0]):
            shade = 1 - amount * min(1.0, (math.hypot(x - cx, y - cy) / farthest) ** 1.6)
            level = int(255 * shade)
            pixels[x, y] = (level, level, level)
    return overlay


def _corner_matte(data: bytes) -> bytes:
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    samples = [
        image.getpixel((0, 0)),
        image.getpixel((image.width - 1, 0)),
        image.getpixel((0, image.height - 1)),
        image.getpixel((image.width - 1, image.height - 1)),
    ]
    key = tuple(sum(channel[i] for channel in samples) // 4 for i in range(3))
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            if _distance((red, green, blue), key) <= _CORNER_TOLERANCE:
                pixels[x, y] = (red, green, blue, 0)
            else:
                pixels[x, y] = (red, green, blue, alpha)
    return _png(image)


def _distance(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right, strict=True)))


def _clip(value: float) -> int:
    return max(0, min(255, int(value)))


def resize_to(data: bytes, width: int, height: int) -> bytes:
    """缩放到指定像素。已是目标尺寸则只保证输出 PNG。"""
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    if image.size != (width, height):
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    return _png(image)


def encode(data: bytes, image_format: str) -> bytes:
    """按格式输出。JPG 铺白底，去掉透明通道。"""
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    if image_format.lower() in {"jpg", "jpeg"}:
        canvas = Image.new("RGB", image.size, (255, 255, 255))
        canvas.paste(image, mask=image.getchannel("A"))
        buffer = io.BytesIO()
        canvas.save(buffer, format="JPEG", quality=92)
        return buffer.getvalue()
    return _png(image)


def letterbox(
    data: bytes,
    width: int,
    height: int,
    fill: tuple[int, int, int, int] = (255, 255, 255, 255),
) -> bytes:
    """完整放入目标画幅，不裁切，空白居中留白。"""
    source = Image.open(io.BytesIO(data)).convert("RGBA")
    if source.size == (width, height):
        return _png(source)
    scale = min(width / source.width, height / source.height)
    size = (
        max(1, int(round(source.width * scale))),
        max(1, int(round(source.height * scale))),
    )
    placed = source.resize(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (width, height), fill)
    canvas.paste(placed, ((width - size[0]) // 2, (height - size[1]) // 2), placed)
    return _png(canvas)


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
