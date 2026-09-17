import asyncio
import copy
import io
import uuid
import zipfile
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import storage
from app.edits.pixels import adjust, encode, letterbox, remove_background
from app.models import Asset, ToolRun
from app.models.asset import AssetKind, AssetSource
from app.models.tool_run import RunStatus
from app.providers import EditRequest, get_image_provider
from app.ratios import DELIVERY_RATIOS, Ratio, cover_size, size_of
from app.schemas.asset import AssetOut
from app.schemas.batch import BatchIn, BatchItemOut, BatchOpIn, BatchOut
from app.schemas.run import RunOut
from app.services import assets as asset_service
from app.services import runs
from app.services.exports import PackedExport
from app.services.images import probe
from app.tools.enhance import ExpandCanvasIn, ReplaceBackgroundIn, UpscaleImageIn
from app.tools.marketing import PrepareDeliverySizesIn
from app.tools.retouch import AdjustIn


class UnknownBatchAsset(Exception):
    pass


class EmptyBatch(Exception):
    pass


def _unique_ratios(values: list[Ratio]) -> list[Ratio]:
    seen: list[Ratio] = []
    for ratio in values:
        if ratio not in seen:
            seen.append(ratio)
    return seen


async def apply_op(data: bytes, operation: BatchOpIn) -> list[bytes]:
    if operation.tool == "remove_background":
        return [await asyncio.to_thread(remove_background, data)]
    if operation.tool == "adjust_image":
        params = AdjustIn.model_validate(operation.params).model_dump()
        params.pop("layer_id", None)
        values = {key: value for key, value in params.items() if value}
        return [await asyncio.to_thread(lambda: adjust(data, **values))]
    if operation.tool == "upscale_image":
        scale = UpscaleImageIn.model_validate(operation.params).scale
        return [await get_image_provider().upscale(data, scale)]
    if operation.tool == "replace_background":
        parsed = ReplaceBackgroundIn.model_validate(operation.params)
        return await get_image_provider().edit(
            EditRequest(
                prompt=f"只替换背景，保持主体、光线和边缘不变。新背景：{parsed.prompt}",
                image=data,
                count=1,
                negative_prompt=parsed.negative_prompt,
            )
        )
    if operation.tool == "expand_canvas":
        parsed = ExpandCanvasIn.model_validate(operation.params)
        meta = probe(data)
        width, height = cover_size(meta.width, meta.height, parsed.ratio)
        return await get_image_provider().edit(
            EditRequest(prompt=parsed.prompt, image=data, width=width, height=height)
        )
    if operation.tool == "prepare_delivery_sizes":
        parsed = PrepareDeliverySizesIn.model_validate(operation.params or {})
        ratios = _unique_ratios(parsed.ratios or list(DELIVERY_RATIOS))
        return [letterbox(data, *size_of(ratio)) for ratio in ratios]
    raise ValueError(f"批量不支持 {operation.tool}")


async def _store(session: AsyncSession, user_id: uuid.UUID, images: list[bytes]) -> list[Asset]:
    created = []
    for data in images:
        created.append(
            await asset_service.create_from_bytes(
                session, user_id, data, AssetKind.EXPORT, AssetSource.TOOL
            )
        )
    return created


async def process_asset(
    session: AsyncSession, user_id: uuid.UUID, source: Asset, payload: BatchIn
) -> list[Asset]:
    data = await storage.get(source.storage_key)
    frames = [data]
    for operation in payload.operations:
        next_frames: list[bytes] = []
        for frame in frames:
            next_frames.extend(await apply_op(frame, operation))
        frames = next_frames
    encoded: list[bytes] = []
    for frame in frames:
        for fmt in payload.formats:
            encoded.append(encode(frame, fmt))
    return await _store(session, user_id, encoded)


def _blank_items(asset_ids: list[str]) -> list[dict]:
    return [
        {"source_id": asset_id, "status": "pending", "error": None, "output_ids": []}
        for asset_id in asset_ids
    ]


async def execute(session: AsyncSession, run: ToolRun) -> dict:
    payload = BatchIn.model_validate(run.params)
    items = _blank_items([str(asset_id) for asset_id in payload.asset_ids])
    total = len(items)
    await runs.report(session, run, 8, "准备批量任务", {"items": copy.deepcopy(items)})

    for index, item in enumerate(items):
        item["status"] = "running"
        await runs.report(
            session,
            run,
            10 + int(80 * index / total),
            f"处理第 {index + 1} / {total} 张",
            {"items": copy.deepcopy(items)},
        )
        source = await asset_service.get_for_user(
            session, run.user_id, uuid.UUID(item["source_id"])
        )
        if source is None:
            item["status"] = "failed"
            item["error"] = "素材不存在"
            continue
        try:
            outputs = await process_asset(session, run.user_id, source, payload)
        except Exception as exc:
            item["status"] = "failed"
            item["error"] = str(exc) or "处理失败"
            continue
        item["status"] = "succeeded"
        item["output_ids"] = [str(asset.id) for asset in outputs]
        await runs.report(
            session,
            run,
            10 + int(80 * (index + 1) / total),
            f"完成第 {index + 1} / {total} 张",
            {"items": copy.deepcopy(items)},
        )

    if all(item["status"] == "failed" for item in items):
        from app.tools.context import ToolError

        raise ToolError(items[0]["error"] or "全部处理失败")
    return {"items": items}


async def require_assets(
    session: AsyncSession, user_id: uuid.UUID, asset_ids: list[uuid.UUID]
) -> list[Asset]:
    found = []
    for asset_id in asset_ids:
        asset = await asset_service.get_for_user(session, user_id, asset_id)
        if asset is None:
            raise UnknownBatchAsset
        found.append(asset)
    return found


async def list_for_user(
    session: AsyncSession, user_id: uuid.UUID, limit: int = 20
) -> list[ToolRun]:
    result = await session.scalars(
        select(ToolRun)
        .where(ToolRun.user_id == user_id, ToolRun.tool == "batch_process")
        .order_by(ToolRun.created_at.desc())
        .limit(limit)
    )
    return list(result)


async def detail(session: AsyncSession, run: ToolRun) -> BatchOut:
    raw_items = (run.result or {}).get("items") or [
        {"source_id": str(asset_id), "status": "pending", "error": None, "output_ids": []}
        for asset_id in (run.params or {}).get("asset_ids") or []
    ]
    items: list[BatchItemOut] = []
    for raw in raw_items:
        source = await asset_service.get_for_user(session, run.user_id, uuid.UUID(raw["source_id"]))
        if source is None:
            continue
        outputs = []
        for output_id in raw.get("output_ids") or []:
            asset = await asset_service.get_for_user(session, run.user_id, uuid.UUID(output_id))
            if asset is not None:
                outputs.append(AssetOut.of(asset))
        items.append(
            BatchItemOut(
                source=AssetOut.of(source),
                status=raw.get("status") or "pending",
                error=raw.get("error"),
                outputs=outputs,
            )
        )
    return BatchOut(run=RunOut.of(run), items=items, created_at=run.created_at)


async def pack(session: AsyncSession, run: ToolRun) -> PackedExport:
    if run.status is not RunStatus.SUCCEEDED:
        raise EmptyBatch
    outputs: list[Asset] = []
    for raw in (run.result or {}).get("items") or []:
        for output_id in raw.get("output_ids") or []:
            asset = await asset_service.get_for_user(session, run.user_id, uuid.UUID(output_id))
            if asset is not None:
                outputs.append(asset)
    if not outputs:
        raise EmptyBatch

    created_at = datetime.now(UTC)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for index, asset in enumerate(outputs, start=1):
            data = await storage.get(asset.storage_key)
            fmt = asset.image_format.upper()
            ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}.get(fmt, "png")
            zipped.writestr(f"images/{index:02d}-{asset.width}x{asset.height}.{ext}", data)
    filename = f"批量导出-{created_at.strftime('%Y%m%d')}.zip"
    return PackedExport(data=archive.getvalue(), filename=filename)
