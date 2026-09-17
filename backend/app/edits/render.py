import io
import os
import uuid

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.layers import Layer, LayerDocument, LayerKind

WHITE = (255, 255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)

_FONT_PATHS = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
)
_font_file: str | None = None


def flatten(
    document: LayerDocument,
    images: dict[uuid.UUID, bytes],
    *,
    background: tuple[int, int, int, int] = WHITE,
    include_text: bool = True,
) -> bytes:
    """按文档合成一张 PNG。旋转绕图层中心，与画布渲染一致。

    include_text 为 false 时跳过文字层，供成层等仍保留矢量字的像素操作使用。
    """
    canvas = Image.new("RGBA", (document.width, document.height), background)
    for layer in document.layers:
        if not layer.visible:
            continue
        if layer.kind is LayerKind.TEXT:
            if include_text:
                _composite_text(canvas, layer)
            continue
        if layer.kind is not LayerKind.IMAGE or layer.asset_id is None:
            continue
        raw = images.get(layer.asset_id)
        if raw is None:
            continue
        source = Image.open(io.BytesIO(raw)).convert("RGBA")
        source = source.resize((layer.width, layer.height), Image.Resampling.LANCZOS)
        _place(canvas, layer, source)

    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


def _composite_text(canvas: Image.Image, layer: Layer) -> None:
    raw = layer.text if layer.text is not None else layer.name
    content = (raw or "").strip()
    if not content:
        return
    width = max(1, layer.width)
    height = max(1, layer.height)
    source = Image.new("RGBA", (width, height), TRANSPARENT)
    draw = ImageDraw.Draw(source)
    font = _font(layer.font_size)
    color = _rgba(layer.fill)
    box = draw.textbbox((0, 0), content, font=font)
    text_w, text_h = box[2] - box[0], box[3] - box[1]
    x = (width - text_w) / 2 - box[0]
    y = (height - text_h) / 2 - box[1]
    draw.text((x, y), content, font=font, fill=color)
    _place(canvas, layer, source)


def _place(canvas: Image.Image, layer: Layer, source: Image.Image) -> None:
    transform = layer.transform
    if transform.scale_x < 0:
        source = ImageOps.mirror(source)
    if transform.scale_y < 0:
        source = ImageOps.flip(source)

    width = max(1, int(round(layer.width * abs(transform.scale_x))))
    height = max(1, int(round(layer.height * abs(transform.scale_y))))
    if source.size != (width, height):
        source = source.resize((width, height), Image.Resampling.LANCZOS)

    if layer.opacity < 1:
        alpha = source.getchannel("A").point(lambda value: int(value * layer.opacity))
        source.putalpha(alpha)

    if transform.rotation:
        # Pillow 逆时针为正，画布旋转顺时针为正
        source = source.rotate(-transform.rotation, expand=True, resample=Image.Resampling.BICUBIC)

    center_x = transform.x + layer.width / 2
    center_y = transform.y + layer.height / 2
    left = int(round(center_x - source.width / 2))
    top = int(round(center_y - source.height / 2))
    _paste(canvas, source, left, top)


def _paste(canvas: Image.Image, source: Image.Image, left: int, top: int) -> None:
    src_x, src_y = max(0, -left), max(0, -top)
    dst_x, dst_y = max(0, left), max(0, top)
    width = min(source.width - src_x, canvas.width - dst_x)
    height = min(source.height - src_y, canvas.height - dst_y)
    if width <= 0 or height <= 0:
        return
    piece = source.crop((src_x, src_y, src_x + width, src_y + height))
    canvas.alpha_composite(piece, (dst_x, dst_y))


def _font(size: float) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = _font_path()
    px = max(8, int(round(size)))
    if path:
        try:
            return ImageFont.truetype(path, px)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=px)
    except TypeError:
        return ImageFont.load_default()


def _font_path() -> str:
    global _font_file
    if _font_file is not None:
        return _font_file
    for path in _FONT_PATHS:
        if os.path.exists(path):
            _font_file = path
            return path
    _font_file = ""
    return ""


def _rgba(fill: str) -> tuple[int, int, int, int]:
    color = fill.lstrip("#")
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    if len(color) != 6:
        return (20, 20, 20, 255)
    return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16), 255)
