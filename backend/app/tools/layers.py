import asyncio
import io

from PIL import Image
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import storage
from app.edits.mask import apply_masked
from app.edits.ocr import detect_text
from app.edits.pixels import remove_background
from app.edits.split import (
    EmptyCut,
    alpha_mask,
    already_promoted,
    already_split,
    as_background_and_object,
    cut_object,
    expand_mask,
    fill_background,
    mask_hash,
    promote_document,
    punch,
    remove_text,
    split_document,
)
from app.layers import BACKGROUND_LAYER_ID, LayerKind
from app.models.asset import Asset, AssetKind, AssetSource
from app.models.tool_run import ToolRun
from app.providers import EditRequest, get_image_provider
from app.services import assets, runs, selections
from app.tools.base import HIDDEN_MASK, MaskRef, ToolSpec
from app.tools.context import ToolError, document_of, flatten_session, require_session
from app.tools.target import require_selection

_RECONSTRUCT = (
    "画面中已有一块被修补过的区域。只把这块修补处修得和周围景物衔接自然，"
    "不要新增人物、动物或物体，也不要改变未修补的部分。"
)


class SplitLayersIn(BaseModel):
    include_text: bool = False


class PromoteIn(MaskRef):
    name: str | None = Field(default=None, max_length=40)


async def _store(session: AsyncSession, run: ToolRun, data: bytes, kind: AssetKind) -> Asset:
    return await assets.create_from_bytes(session, run.user_id, data, kind, AssetSource.TOOL)


async def _fill_hole(session: AsyncSession, run: ToolRun, source: bytes, mask: bytes) -> bytes:
    # 先挖空再填，模型只看到没有主体的图，避免又把主体画回背景
    hole = expand_mask(mask, Image.open(io.BytesIO(source)).size)
    prepared = await asyncio.to_thread(fill_background, source, hole)
    edited = (
        await get_image_provider().edit(
            EditRequest(prompt=_RECONSTRUCT, image=prepared),
            on_progress=lambda progress, stage: runs.report(session, run, progress, stage),
        )
    )[0]
    return apply_masked(prepared, edited, hole)


async def split_layers_exec(session: AsyncSession, run: ToolRun) -> dict:
    record = await require_session(session, run)
    document = document_of(record)
    if already_split(document):
        return {"document": document.model_dump(mode="json")}

    await runs.report(session, run, 15, "读取画布")
    source = await flatten_session(session, record)
    await runs.report(session, run, 35, "分离主体")
    subject = await asyncio.to_thread(remove_background, source)
    mask = alpha_mask(subject)
    await runs.report(session, run, 55, "修复背景")
    background = await _fill_hole(session, run, source, mask)
    texts = []
    if run.params.get("include_text"):
        await runs.report(session, run, 80, "识别文字")
        texts = await asyncio.to_thread(detect_text, source)
        if texts:
            size = Image.open(io.BytesIO(source)).size
            subject, background = await asyncio.to_thread(
                remove_text, subject, background, texts, size
            )

    subject_asset = await _store(session, run, subject, AssetKind.SUBJECT)
    background_asset = await _store(session, run, background, AssetKind.BACKGROUND)
    next_document = split_document(
        document,
        background_id=background_asset.id,
        subject_id=subject_asset.id,
        texts=texts,
        subject_hash=mask_hash(mask),
    )
    await selections.clear(record.id)
    return {
        "document": next_document.model_dump(mode="json"),
        "asset_ids": [str(background_asset.id), str(subject_asset.id)],
    }


async def promote_object_exec(session: AsyncSession, run: ToolRun) -> dict:
    record = await require_session(session, run)
    document = document_of(record)
    if run.params.get("revision") not in (None, record.revision):
        raise ToolError("选区已过期，请重新选择")
    mask = await require_selection(
        session, record, run.params.get("mask_asset_id"), "请先点选或涂抹要拆出的物体"
    )

    key = mask_hash(mask)
    if already_promoted(document, key):
        return {"document": document.model_dump(mode="json")}

    await runs.report(session, run, 20, "读取选区")
    source = await flatten_session(session, record, include_text=False)
    try:
        cut, left, top, width, height = cut_object(source, mask)
    except EmptyCut as exc:
        raise ToolError("选区为空，请重新选择") from exc

    await runs.report(session, run, 45, "修复原位置")
    filled = await _fill_hole(session, run, source, mask)
    object_asset = await _store(session, run, cut, AssetKind.SUBJECT)
    name = run.params.get("name")

    if already_split(document):
        next_document, created = await _promote_onto_split(
            session,
            run,
            document,
            record.user_id,
            filled,
            mask,
            object_asset,
            left,
            top,
            width,
            height,
            key,
        )
    else:
        background_asset = await _store(session, run, filled, AssetKind.BACKGROUND)
        next_document = as_background_and_object(
            document,
            background_id=background_asset.id,
            object_id=object_asset.id,
            x=left,
            y=top,
            width=width,
            height=height,
            source_hash=key,
        )
        created = [background_asset, object_asset]

    if name:
        next_document.layers[-1].name = name
    await selections.clear(record.id)
    return {
        "document": next_document.model_dump(mode="json"),
        "asset_ids": [str(asset.id) for asset in created],
    }


async def _promote_onto_split(
    session: AsyncSession,
    run: ToolRun,
    document,
    user_id,
    filled: bytes,
    mask: bytes,
    object_asset: Asset,
    left: int,
    top: int,
    width: int,
    height: int,
    key: str,
) -> tuple:
    replacements: dict[str, object] = {}
    created = [object_asset]
    for layer in document.layers:
        if layer.kind is not LayerKind.IMAGE or layer.asset_id is None:
            continue
        raw = await assets.get_for_user(session, user_id, layer.asset_id)
        if raw is None:
            continue
        data = await storage.get(raw.storage_key)
        if layer.id == BACKGROUND_LAYER_ID:
            data, kind = apply_masked(data, filled, mask), AssetKind.BACKGROUND
        else:
            data = punch(data, mask, x=layer.transform.x, y=layer.transform.y)
            kind = AssetKind.SUBJECT
        replacement = await _store(session, run, data, kind)
        replacements[layer.id] = replacement.id
        created.append(replacement)

    return (
        promote_document(
            document,
            asset_id=object_asset.id,
            x=left,
            y=top,
            width=width,
            height=height,
            source_hash=key,
            replacements=replacements,
        ),
        created,
    )


SPLIT_LAYERS = ToolSpec(
    name="split_layers",
    label="拆层",
    description=(
        "把画面拆成背景和主体。默认不拆文字；"
        "include_text 为 true 时才识别文字层。已拆过则跳过。"
    ),
    params=SplitLayersIn,
    handler=split_layers_exec,
    queued=True,
    session_required=True,
)

PROMOTE_OBJECT = ToolSpec(
    name="promote_object_to_layer",
    label="提升为图层",
    description=(
        "把当前选区提升为独立图层，原位置用周围背景填补。"
        "该物体已是独立图层时跳过。画布摘要标明已有选区时即可调用。"
    ),
    params=PromoteIn,
    handler=promote_object_exec,
    queued=True,
    session_required=True,
    agent_hidden=HIDDEN_MASK,
)
