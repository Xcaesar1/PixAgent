import enum
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase, enum_column


class AssetKind(enum.StrEnum):
    ORIGINAL = "original"
    GENERATED = "generated"
    SUBJECT = "subject"
    BACKGROUND = "background"
    MASK = "mask"
    MARKETING = "marketing"
    EXPORT = "export"


class AssetSource(enum.StrEnum):
    UPLOAD = "upload"
    GENERATE = "generate"
    TOOL = "tool"


class Asset(UUIDBase):
    __tablename__ = "assets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[AssetKind] = mapped_column(enum_column(AssetKind))
    source: Mapped[AssetSource] = mapped_column(enum_column(AssetSource))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    image_format: Mapped[str] = mapped_column(String(8))
    width: Mapped[int]
    height: Mapped[int]
    size_bytes: Mapped[int]
    has_alpha: Mapped[bool]
