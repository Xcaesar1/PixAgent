"""把评测任务名映射到本地确定性像素函数。"""

from __future__ import annotations

from collections.abc import Callable

from app.edits.pixels import adjust, encode, letterbox, remove_background, resize_to
from app.ratios import DELIVERY_RATIOS, Ratio, size_of

TaskFn = Callable[[bytes, dict], list[tuple[str, bytes]]]


def _one(label: str, data: bytes) -> list[tuple[str, bytes]]:
    return [(label, data)]


def run_remove_background(data: bytes, params: dict) -> list[tuple[str, bytes]]:
    return _one("remove_background", remove_background(data))


def run_adjust_image(data: bytes, params: dict) -> list[tuple[str, bytes]]:
    allowed = {
        "brightness",
        "contrast",
        "highlights",
        "shadows",
        "temperature",
        "tint",
        "saturation",
        "vibrance",
        "sharpness",
        "clarity",
        "vignette",
    }
    kwargs = {key: params[key] for key in allowed if key in params}
    return _one("adjust_image", adjust(data, **kwargs))


def run_letterbox(data: bytes, params: dict) -> list[tuple[str, bytes]]:
    width, height = int(params["width"]), int(params["height"])
    return _one(f"{width}x{height}", letterbox(data, width, height))


def run_prepare_delivery_sizes(data: bytes, params: dict) -> list[tuple[str, bytes]]:
    raw = params.get("ratios") or [ratio.value for ratio in DELIVERY_RATIOS]
    outputs: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    for value in raw:
        ratio = Ratio(value)
        if ratio.value in seen:
            continue
        seen.add(ratio.value)
        width, height = size_of(ratio)
        outputs.append((ratio.value, letterbox(data, width, height)))
    return outputs


def run_encode(data: bytes, params: dict) -> list[tuple[str, bytes]]:
    fmt = str(params.get("format", "png"))
    return _one(fmt, encode(data, fmt))


def run_resize(data: bytes, params: dict) -> list[tuple[str, bytes]]:
    width, height = int(params["width"]), int(params["height"])
    return _one(f"{width}x{height}", resize_to(data, width, height))


TASKS: dict[str, TaskFn] = {
    "remove_background": run_remove_background,
    "adjust_image": run_adjust_image,
    "letterbox": run_letterbox,
    "prepare_delivery_sizes": run_prepare_delivery_sizes,
    "encode": run_encode,
    "resize": run_resize,
}


def run_task(name: str, data: bytes, params: dict | None = None) -> list[tuple[str, bytes]]:
    try:
        handler = TASKS[name]
    except KeyError as exc:
        known = "、".join(TASKS)
        raise ValueError(f"不支持的评测任务：{name}。可选：{known}") from exc
    return handler(data, params or {})
