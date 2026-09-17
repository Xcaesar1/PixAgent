import enum


class Ratio(enum.StrEnum):
    SQUARE = "1:1"
    PORTRAIT_4_5 = "4:5"
    PORTRAIT_3_4 = "3:4"
    VERTICAL_9_16 = "9:16"
    LANDSCAPE_16_9 = "16:9"


# 与交付尺寸对齐，避免生成后再次重采样
SIZES: dict[Ratio, tuple[int, int]] = {
    Ratio.SQUARE: (1080, 1080),
    Ratio.PORTRAIT_4_5: (1080, 1350),
    Ratio.PORTRAIT_3_4: (1080, 1440),
    Ratio.VERTICAL_9_16: (1080, 1920),
    Ratio.LANDSCAPE_16_9: (1920, 1080),
}

DELIVERY_RATIOS = (Ratio.SQUARE, Ratio.PORTRAIT_4_5, Ratio.VERTICAL_9_16)


def size_of(ratio: Ratio) -> tuple[int, int]:
    return SIZES[ratio]


def parts_of(ratio: Ratio) -> tuple[int, int]:
    left, right = ratio.value.split(":")
    return int(left), int(right)


def cover_size(width: int, height: int, ratio: Ratio) -> tuple[int, int]:
    """刚好包住原图的目标比例画幅，扩图时主体不必被裁切。"""
    rw, rh = parts_of(ratio)
    if width * rh >= height * rw:
        return width, max(1, int(width * rh / rw))
    return max(1, int(height * rw / rh)), height


def matches_ratio(width: int, height: int, ratio: Ratio) -> bool:
    rw, rh = parts_of(ratio)
    return width * rh == height * rw


def ratio_of(width: int, height: int) -> Ratio | None:
    for ratio, size in SIZES.items():
        if (width, height) == size:
            return ratio
    for ratio in Ratio:
        if matches_ratio(width, height, ratio):
            return ratio
    return None
