import enum

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.edits.pixels import letterbox, resize_to
from app.models.asset import AssetKind, AssetSource
from app.models.tool_run import ToolRun
from app.providers import EditRequest, get_image_provider
from app.ratios import DELIVERY_RATIOS, Ratio, size_of
from app.services import assets, runs
from app.tools.base import ToolSpec
from app.tools.context import flatten_session, require_session


class MarketingKind(enum.StrEnum):
    PRODUCT = "product"
    SCENE = "scene"
    MODEL = "model"
    POSTER = "poster"


_PROMPTS = {
    MarketingKind.PRODUCT: (
        "把商品放在纯白背景上，居中构图，柔和顶光，边缘干净，"
        "保留商品原有材质与颜色，输出电商主图。"
    ),
    MarketingKind.SCENE: (
        "把商品放到真实生活场景中，侧逆光、浅景深，氛围自然，"
        "保留商品原有材质与颜色。"
    ),
    MarketingKind.MODEL: (
        "生成模特手持或佩戴该商品的半身展示图，简洁室内背景、自然光，"
        "商品细节清晰可辨。"
    ),
    MarketingKind.POSTER: (
        "做一张促销海报，突出商品，右侧或下方留出文字区，构图干净有冲击力。"
    ),
}


class GenerateMarketingIn(BaseModel):
    kind: MarketingKind = Field(
        description="product 商品主图、scene 场景氛围图、model 模特上身、poster 促销海报"
    )
    caption: str | None = Field(default=None, max_length=200, description="海报文案或补充要求")
    count: int = Field(default=1, ge=1, le=4)
    ratio: Ratio = Field(default=Ratio.SQUARE, description="输出比例，默认 1:1")


class PrepareDeliverySizesIn(BaseModel):
    ratios: list[Ratio] = Field(
        default_factory=lambda: list(DELIVERY_RATIOS),
        min_length=1,
        max_length=len(Ratio),
        description="要输出的投放比例。默认 1:1、4:5、9:16。主体不被裁切。",
    )
    prompt: str = Field(
        default="自然延伸画面边缘，保持主体完整，不要裁切商品",
        max_length=500,
    )


async def _store(
    session: AsyncSession,
    run: ToolRun,
    images: list[bytes],
    *,
    kind: AssetKind,
    variants: list[dict],
) -> dict:
    created = [
        await assets.create_from_bytes(session, run.user_id, data, kind, AssetSource.TOOL)
        for data in images
    ]
    labeled = []
    for asset, variant in zip(created, variants, strict=True):
        labeled.append({**variant, "asset_id": str(asset.id)})
    return {"asset_ids": [str(asset.id) for asset in created], "variants": labeled}


async def _progress(session: AsyncSession, run: ToolRun, progress: int, stage: str) -> None:
    await runs.report(session, run, progress, stage)


def _prompt_of(kind: MarketingKind, caption: str | None) -> str:
    text = _PROMPTS[kind]
    extra = (caption or "").strip()
    return f"{text} 文案：{extra}" if extra else text


def _unique(ratios: list[Ratio]) -> list[Ratio]:
    seen: list[Ratio] = []
    for ratio in ratios:
        if ratio not in seen:
            seen.append(ratio)
    return seen


async def generate_marketing_exec(session: AsyncSession, run: ToolRun) -> dict:
    record = await require_session(session, run)
    kind = MarketingKind(run.params["kind"])
    ratio = Ratio(run.params["ratio"])
    width, height = size_of(ratio)
    await runs.report(session, run, 15, "读取画布")
    source = await flatten_session(session, record)
    await runs.report(session, run, 30, "生成营销图")
    images = await get_image_provider().edit(
        EditRequest(
            prompt=_prompt_of(kind, run.params.get("caption")),
            image=source,
            count=run.params["count"],
            width=width,
            height=height,
        ),
        on_progress=lambda progress, stage: _progress(session, run, progress, stage),
    )
    fitted = [resize_to(data, width, height) for data in images]
    await runs.report(session, run, 95, "营销图已加入图片墙")
    return await _store(
        session,
        run,
        fitted,
        kind=AssetKind.MARKETING,
        variants=[{"kind": kind.value, "ratio": ratio.value, "width": width, "height": height}]
        * len(fitted),
    )


async def prepare_delivery_sizes_exec(session: AsyncSession, run: ToolRun) -> dict:
    record = await require_session(session, run)
    ratios = _unique([Ratio(value) for value in run.params["ratios"]])
    await runs.report(session, run, 20, "读取画布")
    source = await flatten_session(session, record)
    images: list[bytes] = []
    variants: list[dict] = []
    total = len(ratios)
    for index, ratio in enumerate(ratios):
        width, height = size_of(ratio)
        await runs.report(session, run, 30 + int(60 * index / total), f"适配 {ratio.value}")
        images.append(letterbox(source, width, height))
        variants.append({"kind": "export", "ratio": ratio.value, "width": width, "height": height})
    await runs.report(session, run, 95, "投放尺寸已加入图片墙")
    return await _store(session, run, images, kind=AssetKind.EXPORT, variants=variants)


GENERATE_MARKETING = ToolSpec(
    name="generate_marketing",
    label="营销图",
    description=(
        "按当前画布生成电商营销图，只进图片墙，不改当前画布。"
        "kind：product 商品主图（白底）、scene 场景氛围图、"
        "model 模特上身、poster 促销海报。caption 可填海报标题或补充要求。"
    ),
    params=GenerateMarketingIn,
    handler=generate_marketing_exec,
    queued=True,
    session_required=True,
)

PREPARE_DELIVERY_SIZES = ToolSpec(
    name="prepare_delivery_sizes",
    label="投放尺寸",
    description=(
        "把当前画布完整放入投放比例，不裁切、不改画面，只进图片墙。"
        "默认一次出 1:1、4:5、9:16。用户说改尺寸、出投放物料时用这个，不要用 crop_canvas。"
    ),
    params=PrepareDeliverySizesIn,
    handler=prepare_delivery_sizes_exec,
    queued=False,
    session_required=True,
)
