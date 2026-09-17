import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app import storage
from app.models.asset import AssetKind, AssetSource
from app.models.tool_run import ToolRun
from app.providers import GenerateRequest, ProviderError, get_image_provider
from app.ratios import Ratio, size_of
from app.services import assets, runs


async def _references(session: AsyncSession, run: ToolRun) -> list[bytes]:
    result: list[bytes] = []
    for raw in run.params.get("reference_asset_ids") or []:
        asset = await assets.get_for_user(session, run.user_id, uuid.UUID(raw))
        if asset is None:
            raise ProviderError("参考图不存在")
        result.append(await storage.get(asset.storage_key))
    return result


async def execute(session: AsyncSession, run: ToolRun) -> dict:
    """执行一次文生图并把候选图转存为素材。

    模型返回的链接 24 小时过期，必须落到自有存储后再对外暴露。
    """

    async def on_progress(progress: int, stage: str) -> None:
        await runs.report(session, run, progress, stage)

    width, height = size_of(Ratio(run.params["ratio"]))
    request = GenerateRequest(
        prompt=run.params["prompt"],
        width=width,
        height=height,
        count=run.params["count"],
        negative_prompt=run.params.get("negative_prompt"),
        seed=run.params.get("seed"),
        references=await _references(session, run),
    )

    images = await get_image_provider().generate(request, on_progress)

    await runs.report(session, run, 90, "保存候选图")
    created = [
        await assets.create_from_bytes(
            session, run.user_id, data, AssetKind.GENERATED, AssetSource.GENERATE
        )
        for data in images
    ]
    return {"asset_ids": [str(asset.id) for asset in created]}
