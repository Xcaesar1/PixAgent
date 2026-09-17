"""像素级指标。素材由调用方提供，这里只算分数。"""

from __future__ import annotations

import io
import math

from PIL import Image

_HIGHER_IS_BETTER = frozenset({"alpha_iou", "psnr", "contain", "size"})
_LOWER_IS_BETTER = frozenset({"mae"})


def open_rgba(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGBA")


def aligned(pred: bytes, expect: bytes) -> tuple[Image.Image, Image.Image]:
    left, right = open_rgba(pred), open_rgba(expect)
    if left.size != right.size:
        left = left.resize(right.size, Image.Resampling.NEAREST)
    return left, right


def mae(pred: bytes, expect: bytes) -> float:
    left, right = aligned(pred, expect)
    pairs = zip(left.tobytes(), right.tobytes(), strict=True)
    total = sum(abs(a - b) for a, b in pairs)
    count = left.width * left.height * 4
    return total / count if count else 0.0


def psnr(pred: bytes, expect: bytes) -> float:
    left, right = aligned(pred, expect)
    pairs = zip(left.tobytes(), right.tobytes(), strict=True)
    total = sum((a - b) ** 2 for a, b in pairs)
    count = left.width * left.height * 4
    mse = total / count if count else 0.0
    if mse == 0:
        return 99.0
    return 10 * math.log10(255 * 255 / mse)


def _alpha_mask(image: Image.Image, threshold: int) -> list[bool]:
    raw = image.tobytes()
    if "A" in image.getbands():
        return [raw[i + 3] > threshold for i in range(0, len(raw), 4)]
    return [sum(raw[i : i + 3]) / 3 > threshold for i in range(0, len(raw), 3)]


def alpha_iou(pred: bytes, expect: bytes, threshold: int = 128) -> float:
    left, right = aligned(pred, expect)
    pred_mask = _alpha_mask(left, threshold)
    expect_mask = _alpha_mask(right, threshold)
    inter = sum(a and b for a, b in zip(pred_mask, expect_mask, strict=True))
    union = sum(a or b for a, b in zip(pred_mask, expect_mask, strict=True))
    return inter / union if union else 1.0


def image_size(data: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(data)).size


def size_score(data: bytes, width: int, height: int) -> float:
    return 1.0 if image_size(data) == (width, height) else 0.0


def subject_bbox(data: bytes, threshold: int = 16) -> tuple[int, int, int, int] | None:
    """不透明像素的外接框。全透明则返回 None。"""
    image = open_rgba(data)
    xs, ys = [], []
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            if pixels[x, y][3] > threshold:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def contain(source: bytes, output: bytes) -> float:
    """letterbox 后源图主体框仍落在输出画幅内的比例。"""
    src = open_rgba(source)
    out = open_rgba(output)
    box = subject_bbox(source) or (0, 0, src.width, src.height)
    scale = min(out.width / src.width, out.height / src.height)
    offset_x = (out.width - src.width * scale) / 2
    offset_y = (out.height - src.height * scale) / 2
    x0, y0, x1, y1 = box
    left = offset_x + x0 * scale
    top = offset_y + y0 * scale
    right = offset_x + x1 * scale
    bottom = offset_y + y1 * scale
    area = max(0.0, right - left) * max(0.0, bottom - top)
    if area == 0:
        return 1.0
    ix0, iy0 = max(0.0, left), max(0.0, top)
    ix1, iy1 = min(float(out.width), right), min(float(out.height), bottom)
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    return inter / area


def passes(name: str, value: float, threshold: float) -> bool:
    if name in _LOWER_IS_BETTER:
        return value <= threshold
    if name in _HIGHER_IS_BETTER:
        return value >= threshold
    return value >= threshold
