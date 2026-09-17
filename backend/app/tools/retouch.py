import asyncio

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.edits.pixels import adjust, remove_background
from app.models.asset import AssetKind
from app.models.tool_run import ToolRun
from app.services import runs
from app.tools.base import LayerRef, ToolSpec
from app.tools.context import document_of, require_session
from app.tools.target import layer_image, resolve_target, write_layer_image

_LAYER = "layer_id"


class RemoveBackgroundIn(LayerRef):
    pass


class AdjustIn(LayerRef):
    brightness: float = Field(default=0, ge=-1, le=1)
    contrast: float = Field(default=0, ge=-1, le=1)
    highlights: float = Field(default=0, ge=-1, le=1)
    shadows: float = Field(default=0, ge=-1, le=1)
    temperature: float = Field(default=0, ge=-1, le=1)
    tint: float = Field(default=0, ge=-1, le=1)
    saturation: float = Field(default=0, ge=-1, le=1)
    vibrance: float = Field(default=0, ge=-1, le=1)
    sharpness: float = Field(default=0, ge=-1, le=1)
    clarity: float = Field(default=0, ge=-1, le=1)
    vignette: float = Field(default=0, ge=0, le=1)


async def remove_background_exec(session: AsyncSession, run: ToolRun) -> dict:
    record = await require_session(session, run)
    layer = resolve_target(document_of(record), run.params.get(_LAYER))
    await runs.report(session, run, 20, "识别主体")
    data = await layer_image(session, record, layer)
    await runs.report(session, run, 50, "去除背景")
    output = await asyncio.to_thread(remove_background, data)
    return await write_layer_image(session, run, record, layer.id, output, AssetKind.SUBJECT)


async def adjust_image_exec(session: AsyncSession, run: ToolRun) -> dict:
    record = await require_session(session, run)
    layer = resolve_target(document_of(record), run.params.get(_LAYER))
    await runs.report(session, run, 20, "读取图层")
    data = await layer_image(session, record, layer)
    params = {key: value for key, value in run.params.items() if value and key != _LAYER}
    await runs.report(session, run, 60, "调整色彩")
    output = await asyncio.to_thread(lambda: adjust(data, **params))
    return await write_layer_image(session, run, record, layer.id, output, AssetKind.GENERATED)


REMOVE_BACKGROUND = ToolSpec(
    name="remove_background",
    label="去背景",
    description="识别指定图层的主体并去掉背景。默认最上层图像。不要用它来换背景或生成新画面。",
    params=RemoveBackgroundIn,
    handler=remove_background_exec,
    queued=True,
    session_required=True,
)

ADJUST_IMAGE = ToolSpec(
    name="adjust_image",
    label="调色",
    description=(
        "调整指定图层的亮度、对比度、高光、阴影、色温、色调、饱和度、自然饱和度、锐化、清晰度和晕影。"
        "默认最上层图像。参数取值 -1 到 1，晕影为 0 到 1。未提到的参数保持 0。"
        "改成某个具体颜色或换材质要用 replace_region，不要用它。"
    ),
    params=AdjustIn,
    handler=adjust_image_exec,
    queued=True,
    session_required=True,
)
