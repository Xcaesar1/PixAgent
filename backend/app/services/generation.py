import uuid
from dataclasses import replace

from sqlalchemy.ext.asyncio import AsyncSession

from app import storage
from app.models.asset import AssetKind, AssetSource
from app.models.tool_run import ToolRun
from app.providers import GenerateRequest, ProviderError, get_image_provider
from app.providers.generation_modes import is_gpt_mode, validate_generation
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

    selected = validate_generation(run.params)["provider"]
    provider = get_image_provider(selected)
    if is_gpt_mode(selected):
        # Each single-image task is checkpointed independently before submission.
        slots = [dict(item) for item in run.params.get("_gpt_images", [])]
        if not slots and run.params.get("_submission_started"):
            slots.append({"started": True, "task_id": run.params.get("_upstream_task_id")})
        while len(slots) < request.count:
            slots.append({})

        async def checkpoint() -> None:
            run.params = {**run.params, "_gpt_images": [dict(item) for item in slots]}
            await session.commit()

        for index, slot in enumerate(slots):
            if slot.get("asset_id"):
                continue
            task_id = slot.get("task_id")
            if slot.get("started") and not task_id:
                raise ProviderError("GPT 提交结果未确认，为避免重复生成已停止，请管理员查看站点任务")
            slot["started"] = True
            await checkpoint()

            async def on_submitted(upstream_id: str) -> None:
                slot["task_id"] = upstream_id
                await checkpoint()

            async def image_progress(progress: int, stage: str) -> None:
                await on_progress(
                    int(90 * (index + progress / 100) / request.count),
                    f"GPT 第 {index + 1}/{request.count} 张：{stage}",
                )

            await image_progress(0, "开始生成")
            images = await provider.generate(
                replace(request, count=1), image_progress,
                task_id=task_id, on_submitted=on_submitted,
            )
            if len(images) != 1:
                raise ProviderError("GPT 单张任务返回数量异常，已停止后续生成")
            asset = await assets.create_from_bytes(
                session, run.user_id, images[0], AssetKind.GENERATED, AssetSource.GENERATE
            )
            slot["asset_id"] = str(asset.id)
            await checkpoint()
            await image_progress(100, "已保存")
        return {"asset_ids": [item["asset_id"] for item in slots], "provider": selected}
    else:
        images = await provider.generate(request, on_progress)

    await runs.report(session, run, 90, "保存候选图")
    created = [
        await assets.create_from_bytes(
            session, run.user_id, data, AssetKind.GENERATED, AssetSource.GENERATE
        )
        for data in images
    ]
    return {"asset_ids": [str(asset.id) for asset in created], "provider": selected}
