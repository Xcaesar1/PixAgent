"""工具注册表。新增工具在此登记即可同时对界面与 Agent 生效。"""

from app.tools.base import ToolSpec, UnknownTool
from app.tools.batch import BATCH_PROCESS
from app.tools.canvas import (
    CROP_CANVAS,
    FLIP_LAYER,
    MOVE_LAYER,
    REORDER_LAYER,
    ROTATE_LAYER,
    SCALE_LAYER,
    SET_LAYER_OPACITY,
    SET_LAYER_TEXT,
    SET_LAYER_VISIBLE,
)
from app.tools.enhance import EXPAND_CANVAS, REPLACE_BACKGROUND, UPSCALE_IMAGE
from app.tools.generate import GENERATE_IMAGE
from app.tools.layers import PROMOTE_OBJECT, SPLIT_LAYERS
from app.tools.marketing import GENERATE_MARKETING, PREPARE_DELIVERY_SIZES
from app.tools.region import ERASE_REGION, REPLACE_REGION
from app.tools.retouch import ADJUST_IMAGE, REMOVE_BACKGROUND

SPECS: tuple[ToolSpec, ...] = (
    GENERATE_IMAGE,
    REPLACE_BACKGROUND,
    EXPAND_CANVAS,
    UPSCALE_IMAGE,
    REMOVE_BACKGROUND,
    ADJUST_IMAGE,
    ERASE_REGION,
    REPLACE_REGION,
    SPLIT_LAYERS,
    PROMOTE_OBJECT,
    GENERATE_MARKETING,
    PREPARE_DELIVERY_SIZES,
    BATCH_PROCESS,
    CROP_CANVAS,
    FLIP_LAYER,
    SET_LAYER_OPACITY,
    SET_LAYER_VISIBLE,
    SET_LAYER_TEXT,
    REORDER_LAYER,
    SCALE_LAYER,
    ROTATE_LAYER,
    MOVE_LAYER,
)

_BY_NAME = {spec.name: spec for spec in SPECS}


def spec_of(name: str) -> ToolSpec:
    spec = _BY_NAME.get(name)
    if spec is None:
        raise UnknownTool(f"未注册的工具：{name}")
    return spec


def label_of(name: str, params: dict | None = None) -> str:
    spec = _BY_NAME.get(name)
    return spec.label_for(params) if spec else name


__all__ = ["SPECS", "ToolSpec", "UnknownTool", "label_of", "spec_of"]
