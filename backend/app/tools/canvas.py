from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.edits.document import (
    EditError,
    crop,
    flip,
    move,
    reorder,
    rotate,
    scale,
    set_opacity,
    set_text,
    set_visible,
)
from app.layers import LayerMissing
from app.models import ToolRun
from app.ratios import Ratio
from app.tools.base import LayerRef, ToolSpec
from app.tools.context import ToolError, document_of, require_session

_LAYER = "layer_id"
# 拖角缩放同时移动中心，位置由界面算好回填，模型只管倍率
_PLACEMENT = ("x", "y")
# 多步计划里两次翻转要能分辨先横后竖
_FLIP_LABELS = {"horizontal": "水平翻转", "vertical": "垂直翻转"}


class FlipIn(LayerRef):
    direction: Literal["horizontal", "vertical"]


class OpacityIn(LayerRef):
    opacity: float = Field(ge=0, le=1)


class VisibleIn(LayerRef):
    visible: bool


class TextIn(LayerRef):
    text: str = Field(max_length=500)
    font_size: float | None = Field(default=None, ge=8, le=400)
    fill: str | None = Field(default=None, pattern=r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class ScaleIn(LayerRef):
    factor: float | None = Field(default=None, gt=0, le=8)
    scale_x: float | None = Field(default=None, gt=0, le=8)
    scale_y: float | None = Field(default=None, gt=0, le=8)
    x: float | None = None
    y: float | None = None

    @model_validator(mode="after")
    def _need_target(self) -> "ScaleIn":
        if self.factor is None and self.scale_x is None and self.scale_y is None:
            raise ValueError("需要相对倍率或绝对缩放")
        return self


class RotateIn(LayerRef):
    angle: float | None = Field(default=None, ge=-360, le=360)
    rotation: float | None = Field(default=None, ge=-360, le=360)

    @model_validator(mode="after")
    def _need_angle(self) -> "RotateIn":
        if self.angle is None and self.rotation is None:
            raise ValueError("需要旋转角度")
        return self


class ReorderIn(LayerRef):
    place: Literal["top", "bottom", "up", "down"]


class MoveIn(LayerRef):
    x: float | None = None
    y: float | None = None
    dx: float | None = None
    dy: float | None = None

    @model_validator(mode="after")
    def _need_delta(self) -> "MoveIn":
        if self.x is None and self.y is None and self.dx is None and self.dy is None:
            raise ValueError("需要坐标或位移")
        return self


class CropRect(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _inside(self) -> "CropRect":
        if self.x + self.width > 1.0001 or self.y + self.height > 1.0001:
            raise ValueError("裁剪框超出画布")
        return self


class CropIn(BaseModel):
    ratio: Ratio | None = None
    rect: CropRect | None = None

    @model_validator(mode="after")
    def _need_one(self) -> "CropIn":
        if (self.ratio is None) == (self.rect is None):
            raise ValueError("裁剪需要比例或裁剪框之一")
        return self


async def _apply(session: AsyncSession, run: ToolRun, mutate) -> dict:
    record = await require_session(session, run)
    try:
        document = mutate(document_of(record), run.params)
    except (LayerMissing, EditError) as exc:
        raise ToolError(str(exc)) from exc
    return {"document": document.model_dump(mode="json")}


async def flip_layer(session: AsyncSession, run: ToolRun) -> dict:
    return await _apply(
        session,
        run,
        lambda doc, params: flip(doc, params.get(_LAYER), params["direction"]),
    )


async def set_layer_opacity(session: AsyncSession, run: ToolRun) -> dict:
    return await _apply(
        session,
        run,
        lambda doc, params: set_opacity(doc, params.get(_LAYER), params["opacity"]),
    )


async def set_layer_visible(session: AsyncSession, run: ToolRun) -> dict:
    return await _apply(
        session,
        run,
        lambda doc, params: set_visible(doc, params.get(_LAYER), params["visible"]),
    )


async def set_layer_text(session: AsyncSession, run: ToolRun) -> dict:
    return await _apply(
        session,
        run,
        lambda doc, params: set_text(
            doc,
            params.get(_LAYER),
            params["text"],
            font_size=params.get("font_size"),
            fill=params.get("fill"),
        ),
    )


async def scale_layer(session: AsyncSession, run: ToolRun) -> dict:
    return await _apply(
        session,
        run,
        lambda doc, params: scale(
            doc,
            params.get(_LAYER),
            factor=params.get("factor"),
            scale_x=params.get("scale_x"),
            scale_y=params.get("scale_y"),
            x=params.get("x"),
            y=params.get("y"),
        ),
    )


async def rotate_layer(session: AsyncSession, run: ToolRun) -> dict:
    return await _apply(
        session,
        run,
        lambda doc, params: rotate(
            doc,
            params.get(_LAYER),
            angle=params.get("angle"),
            rotation=params.get("rotation"),
        ),
    )


async def move_layer(session: AsyncSession, run: ToolRun) -> dict:
    return await _apply(
        session,
        run,
        lambda doc, params: move(
            doc,
            params.get(_LAYER),
            x=params.get("x"),
            y=params.get("y"),
            dx=params.get("dx"),
            dy=params.get("dy"),
        ),
    )


async def reorder_layer(session: AsyncSession, run: ToolRun) -> dict:
    return await _apply(
        session,
        run,
        lambda doc, params: reorder(doc, params.get(_LAYER), params["place"]),
    )


async def crop_canvas(session: AsyncSession, run: ToolRun) -> dict:
    def mutate(doc, params):
        rect = params.get("rect")
        box = (rect["x"], rect["y"], rect["width"], rect["height"]) if rect else None
        ratio = Ratio(params["ratio"]) if params.get("ratio") else None
        return crop(doc, ratio=ratio, rect=box)

    return await _apply(session, run, mutate)


def _canvas(
    name: str,
    label: str,
    description: str,
    params,
    handler,
    hidden: tuple[str, ...] = (),
    detail=None,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        label=label,
        description=description,
        params=params,
        handler=handler,
        queued=False,
        session_required=True,
        agent_hidden=hidden,
        detail=detail,
    )


CROP_CANVAS = _canvas(
    "crop_canvas",
    "裁剪",
    "按比例或归一化矩形裁切画布。只改图层文档，不调用生成模型。",
    CropIn,
    crop_canvas,
)
FLIP_LAYER = _canvas(
    "flip_layer",
    "翻转",
    "水平或垂直翻转指定图层，默认最上层图像。",
    FlipIn,
    flip_layer,
    detail=lambda params: _FLIP_LABELS.get(params.get("direction")),
)
SET_LAYER_OPACITY = _canvas(
    "set_layer_opacity",
    "透明度",
    "设置图层透明度，取值 0 到 1。",
    OpacityIn,
    set_layer_opacity,
)
SET_LAYER_VISIBLE = _canvas(
    "set_layer_visible",
    "显隐",
    "显示或隐藏指定图层，不删除内容。",
    VisibleIn,
    set_layer_visible,
)
SET_LAYER_TEXT = _canvas(
    "set_layer_text",
    "改文字",
    "修改文字图层的文案，可选字号与颜色。未指定图层时改最上层可见文字。",
    TextIn,
    set_layer_text,
)
REORDER_LAYER = _canvas(
    "reorder_layer",
    "图层顺序",
    "调整图层前后顺序：top / bottom / up / down。",
    ReorderIn,
    reorder_layer,
)
SCALE_LAYER = _canvas(
    "scale_layer",
    "缩放",
    "缩放指定图层，默认最上层图像。factor 为相对倍率，scale_x / scale_y 为绝对值。",
    ScaleIn,
    scale_layer,
    _PLACEMENT,
)
ROTATE_LAYER = _canvas(
    "rotate_layer",
    "旋转",
    "旋转图层。angle 为相对角度，rotation 为绝对角度，顺时针为正。",
    RotateIn,
    rotate_layer,
)
MOVE_LAYER = _canvas(
    "move_layer",
    "移动",
    "移动指定图层。x/y 为绝对坐标，dx/dy 为相对像素位移。默认最上层图像。",
    MoveIn,
    move_layer,
)
