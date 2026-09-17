import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import storage
from app.models import Asset, EditSession, SessionAsset
from app.models.asset import AssetKind, AssetSource
from app.services.images import ImageMeta, probe

# 遮罩、抠图层是会话内部产物，创作页历史素材不单独摊开
_WORKING = {AssetKind.MASK, AssetKind.SUBJECT, AssetKind.BACKGROUND}
ORPHAN_TITLE = "未归入会话"


def _storage_key(user_id: uuid.UUID, asset_id: uuid.UUID, extension: str) -> str:
    return f"users/{user_id}/{asset_id}.{extension}"


async def create_from_bytes(
    session: AsyncSession,
    user_id: uuid.UUID,
    data: bytes,
    kind: AssetKind,
    source: AssetSource,
    meta: ImageMeta | None = None,
) -> Asset:
    """校验图片、写入对象存储并落库。所有素材以 user_id 为前缀隔离。"""
    meta = meta or probe(data)
    asset_id = uuid.uuid4()
    key = _storage_key(user_id, asset_id, meta.extension)

    await storage.put(key, data, meta.content_type)

    asset = Asset(
        id=asset_id,
        user_id=user_id,
        kind=kind,
        source=source,
        storage_key=key,
        image_format=meta.image_format,
        width=meta.width,
        height=meta.height,
        size_bytes=meta.size_bytes,
        has_alpha=meta.has_alpha,
    )
    session.add(asset)
    await session.commit()
    return asset


async def list_for_user(session: AsyncSession, user_id: uuid.UUID, limit: int = 50) -> list[Asset]:
    result = await session.scalars(
        select(Asset).where(Asset.user_id == user_id).order_by(Asset.created_at.desc()).limit(limit)
    )
    return list(result)


async def get_for_user(
    session: AsyncSession, user_id: uuid.UUID, asset_id: uuid.UUID
) -> Asset | None:
    """按主键与 user_id 联合查询，避免越权访问他人素材。"""
    return await session.scalar(select(Asset).where(Asset.id == asset_id, Asset.user_id == user_id))


def _visible(assets: list[Asset]) -> list[Asset]:
    return [asset for asset in assets if asset.kind not in _WORKING]


async def library_for_user(
    session: AsyncSession, user_id: uuid.UUID, limit: int = 50
) -> list[tuple[EditSession | None, Asset, list[Asset]]]:
    """创作页素材：按会话收拢，未进过会话的生成/上传单独一组。"""
    records = list(
        await session.scalars(
            select(EditSession)
            .where(EditSession.user_id == user_id)
            .order_by(EditSession.updated_at.desc())
            .limit(limit)
        )
    )
    walls: dict[uuid.UUID, list[Asset]] = defaultdict(list)
    attached: set[uuid.UUID] = set()
    if records:
        rows = await session.execute(
            select(SessionAsset.session_id, Asset)
            .join(Asset, Asset.id == SessionAsset.asset_id)
            .where(SessionAsset.session_id.in_([record.id for record in records]))
            .order_by(SessionAsset.position)
        )
        for session_id, asset in rows:
            walls[session_id].append(asset)
            attached.add(asset.id)

    cover_ids = {record.current_asset_id for record in records}
    covers = {
        asset.id: asset
        for asset in await session.scalars(select(Asset).where(Asset.id.in_(cover_ids)))
    } if cover_ids else {}

    groups: list[tuple[EditSession | None, Asset, list[Asset]]] = []
    for record in records:
        visible = _visible(walls.get(record.id, []))
        cover = covers.get(record.current_asset_id)
        if cover is None and visible:
            cover = visible[0]
        if cover is None:
            continue
        groups.append((record, cover, visible or [cover]))

    leftover = list(
        await session.scalars(
            select(Asset)
            .where(
                Asset.user_id == user_id,
                Asset.kind.notin_(_WORKING),
                *([Asset.id.notin_(attached)] if attached else []),
            )
            .order_by(Asset.created_at.desc())
            .limit(limit)
        )
    )
    if leftover:
        groups.append((None, leftover[0], leftover))
    return groups
