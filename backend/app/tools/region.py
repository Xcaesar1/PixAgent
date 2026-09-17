from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.edits.mask import apply_masked
from app.edits.split import EmptyCut, alpha_mask
from app.layers import Layer, LayerDocument
from app.models.asset import AssetKind
from app.models.tool_run import ToolRun
from app.providers import EditRequest, get_image_provider
from app.services import runs, selections
from app.tools.base import HIDDEN_MASK, LayerRef, MaskRef, ToolSpec
from app.tools.context import ToolError, document_of, require_session
from app.tools.target import (
    layer_image,
    layer_under_mask,
    mask_for_layer,
    resolve_target,
    selection_mask,
    write_layer_image,
)


class RegionIn(LayerRef, MaskRef):
    prompt: str = Field(default="", max_length=500)


class ReplaceRegionIn(LayerRef, MaskRef):
    prompt: str = Field(min_length=1, max_length=500)


def _target(document: LayerDocument, layer_id: str | None, mask: bytes | None) -> Layer:
    """点名了图层就改那一层；否则取选区下最上层，没选区就取最上层图像。"""
    if not layer_id and mask is not None:
        return layer_under_mask(document, mask)
    return resolve_target(document, layer_id)


def _region(source: bytes, mask: bytes | None, layer: Layer, canvas: tuple[int, int]) -> bytes:
    """无选区就用该层透明通道当区域改整层；有选区则取与该层的交集。"""
    if mask is None:
        return alpha_mask(source)
    try:
        return mask_for_layer(mask, layer, canvas)
    except EmptyCut as exc:
        raise ToolError("选区没有覆盖到该图层") from exc


async def _edit_region(session: AsyncSession, run: ToolRun, *, scoped: str, whole: str) -> dict:
    """按「图层 × 选区」改一层：有选区只改选区内，没选区改整层。"""
    record = await require_session(session, run)
    if run.params.get("revision") not in (None, record.revision):
        raise ToolError("选区已过期，请重新选择")

    document = document_of(record)
    mask = await selection_mask(session, record, run.params.get("mask_asset_id"))
    layer = _target(document, run.params.get("layer_id"), mask)

    await runs.report(session, run, 20, "读取图层")
    source = await layer_image(session, record, layer)
    local_mask = _region(source, mask, layer, (document.width, document.height))
    await runs.report(session, run, 40, "局部生成")
    edited = (
        await get_image_provider().edit(
            EditRequest(prompt=whole if mask is None else scoped, image=source),
            on_progress=lambda progress, stage: runs.report(session, run, progress, stage),
        )
    )[0]
    await runs.report(session, run, 85, "合并结果")
    output = apply_masked(source, edited, local_mask)
    await selections.clear(record.id)
    return await write_layer_image(session, run, record, layer.id, output, AssetKind.GENERATED)


async def erase_region_exec(session: AsyncSession, run: ToolRun) -> dict:
    asked = run.params.get("prompt")
    return await _edit_region(
        session,
        run,
        scoped=asked or "移除选中物体，用周围背景自然填补，不要改变选区以外的画面。",
        whole=asked or "移除画面中的物体，用周围背景自然填补。",
    )


async def replace_region_exec(session: AsyncSession, run: ToolRun) -> dict:
    what = run.params["prompt"]
    return await _edit_region(
        session,
        run,
        scoped=f"只改选中区域：{what}。选区外的主体、光线和背景必须保持原样。",
        whole=f"{what}。保持构图、透视与画幅不变，透明区域仍然透明。",
    )


ERASE_REGION = ToolSpec(
    name="erase_region",
    label="局部消除",
    description=(
        "消除物体，并用周围内容自然填补。"
        "有选区时只消除选区内；用 layer_id 点名图层时消除该层内容；两者都有取交集。"
    ),
    params=RegionIn,
    handler=erase_region_exec,
    queued=True,
    session_required=True,
    agent_hidden=HIDDEN_MASK,
)

REPLACE_REGION = ToolSpec(
    name="replace_region",
    label="局部替换",
    description=(
        "按文字描述替换画面内容，改颜色、换材质、换成另一个物体都用它。"
        "有选区时只改选区内；用 layer_id 点名图层时改该层整层；两者都有取交集。"
        "只需给出替换描述，不必确认选区是否点准。"
    ),
    params=ReplaceRegionIn,
    handler=replace_region_exec,
    queued=True,
    session_required=True,
    agent_hidden=HIDDEN_MASK,
)
