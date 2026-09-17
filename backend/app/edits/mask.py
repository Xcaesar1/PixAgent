import io

from PIL import Image, ImageChops, ImageDraw, ImageFilter


def to_luma(data: bytes, size: tuple[int, int] | None = None) -> Image.Image:
    mask = Image.open(io.BytesIO(data))
    if mask.mode in {"RGBA", "LA"}:
        mask = mask.split()[-1]
    else:
        mask = mask.convert("L")
    if size and mask.size != size:
        mask = mask.resize(size, Image.Resampling.NEAREST)
    return mask


def overlay_png(mask: Image.Image, *, color: tuple[int, int, int] = (95, 152, 173)) -> bytes:
    """选区可视化：选中处半透明着色，其余全透明。"""
    luma = mask.convert("L")
    overlay = Image.new("RGBA", luma.size, (*color, 0))
    pixels = overlay.load()
    levels = luma.load()
    for y in range(luma.height):
        for x in range(luma.width):
            alpha = levels[x, y]
            if alpha:
                pixels[x, y] = (*color, 255)
    return _png(overlay)


def rasterize_strokes(
    size: tuple[int, int],
    strokes: list[list[tuple[float, float]]],
    *,
    radius: float,
    base: Image.Image | None = None,
) -> Image.Image:
    """笔画自动闭合成面积：圈住物体就选中整块，短笔画仍只得一条带子。"""
    mask = base.convert("L") if base is not None else Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    width, height = size
    brush = max(2, int(min(width, height) * radius))
    for stroke in strokes:
        if not stroke:
            continue
        points = [(x * width, y * height) for x, y in stroke]
        if len(points) == 1:
            _dot(draw, points[0], brush)
            continue
        if len(points) > 2:
            draw.polygon(points, fill=255)
        # 轮廓带兜底：自相交的乱涂即使填不出内部，涂过的地方也一定被选中
        draw.line(points, fill=255, width=brush, joint="curve")
        for point in points:
            _dot(draw, point, brush)
    return mask


def union(left: Image.Image, right: Image.Image) -> Image.Image:
    return ImageChops.lighter(left.convert("L"), right.convert("L"))


def apply_masked(source: bytes, edited: bytes, mask: bytes) -> bytes:
    """只把选区内的像素换成编辑结果，选区外保持原图。"""
    original = Image.open(io.BytesIO(source)).convert("RGBA")
    result = Image.open(io.BytesIO(edited)).convert("RGBA")
    if result.size != original.size:
        result = result.resize(original.size, Image.Resampling.LANCZOS)
    luma = to_luma(mask, original.size).filter(ImageFilter.GaussianBlur(1.2))
    return _png(Image.composite(result, original, luma))


def _dot(draw: ImageDraw.ImageDraw, point: tuple[float, float], brush: int) -> None:
    x, y = point
    r = brush / 2
    draw.ellipse((x - r, y - r, x + r, y + r), fill=255)


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
