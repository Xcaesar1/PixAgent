import uuid
from datetime import datetime

from pydantic import BaseModel

from app import storage
from app.models import Asset
from app.models.asset import AssetKind, AssetSource


class AssetOut(BaseModel):
    id: uuid.UUID
    kind: AssetKind
    source: AssetSource
    image_format: str
    width: int
    height: int
    size_bytes: int
    has_alpha: bool
    created_at: datetime
    url: str

    @classmethod
    def of(cls, asset: Asset) -> "AssetOut":
        return cls(
            id=asset.id,
            kind=asset.kind,
            source=asset.source,
            image_format=asset.image_format,
            width=asset.width,
            height=asset.height,
            size_bytes=asset.size_bytes,
            has_alpha=asset.has_alpha,
            created_at=asset.created_at,
            url=storage.signed_url(asset.storage_key),
        )


class LibraryGroupOut(BaseModel):
    session_id: uuid.UUID | None
    title: str
    updated_at: datetime
    cover: AssetOut
    assets: list[AssetOut]
