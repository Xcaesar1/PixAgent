import io
import json
import re
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession

from app import storage
from app.models import Asset, EditSession
from app.ratios import ratio_of
from app.schemas.export import EXPORT_KINDS, ExportItemOut, ExportManifestOut
from app.services import sessions
from app.services.images import EXTENSIONS, probe
from app.tools.context import flatten_session


class UnknownExportAsset(Exception):
    pass


@dataclass(frozen=True)
class PackedExport:
    data: bytes
    filename: str
    manifest: ExportManifestOut | None = None

    @property
    def disposition(self) -> str:
        return f"attachment; filename*=UTF-8''{quote(self.filename)}"


def _safe_name(title: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff\- ]+", "", title).strip()
    return (cleaned.replace(" ", "-") or "物料")[:40]


def _extension(asset: Asset | None) -> str:
    if asset is None:
        return "png"
    return EXTENSIONS.get(asset.image_format.upper(), "png")


def _pick(wall: list[Asset], asset_ids: list[uuid.UUID]) -> list[Asset]:
    by_id = {asset.id: asset for asset in wall}
    if asset_ids:
        chosen = []
        for asset_id in asset_ids:
            asset = by_id.get(asset_id)
            if asset is None:
                raise UnknownExportAsset
            chosen.append(asset)
        return chosen
    return [asset for asset in wall if asset.kind in EXPORT_KINDS]


async def _pixels(session: AsyncSession, record: EditSession, asset: Asset | None) -> bytes:
    if asset is None or asset.id == record.current_asset_id:
        return await flatten_session(session, record)
    return await storage.get(asset.storage_key)


async def pack(
    session: AsyncSession, record: EditSession, asset_ids: list[uuid.UUID]
) -> PackedExport:
    wall = await sessions.assets_of(session, record)
    chosen = _pick(wall, asset_ids)
    entries: list[tuple[Asset | None, bytes]] = []
    if chosen:
        for asset in chosen:
            entries.append((asset, await _pixels(session, record, asset)))
    else:
        entries.append((None, await flatten_session(session, record)))

    created_at = datetime.now(UTC)
    items: list[ExportItemOut] = []
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for index, (asset, data) in enumerate(entries, start=1):
            meta = probe(data)
            ratio = ratio_of(meta.width, meta.height)
            flattened = asset is None or asset.id == record.current_asset_id
            kind = "canvas" if flattened else asset.kind.value
            slug = (ratio.value if ratio else f"{meta.width}x{meta.height}").replace(":", "x")
            name = f"images/{index:02d}-{kind}-{slug}.{'png' if flattened else _extension(asset)}"
            zipped.writestr(name, data)
            items.append(
                ExportItemOut(
                    file=name,
                    kind=kind,
                    ratio=ratio.value if ratio else None,
                    width=meta.width,
                    height=meta.height,
                    asset_id=asset.id if asset else None,
                )
            )
        manifest = ExportManifestOut(
            title=record.title,
            session_id=record.id,
            created_at=created_at,
            items=items,
        )
        zipped.writestr(
            "manifest.json",
            json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2),
        )

    filename = f"{_safe_name(record.title)}-{created_at.strftime('%Y%m%d')}.zip"
    return PackedExport(data=archive.getvalue(), filename=filename, manifest=manifest)
