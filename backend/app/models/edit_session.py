import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TIMESTAMPTZ, UUIDBase


class EditSession(UUIDBase):
    """编辑页左栏的一条对话。document 是该会话当前画布的权威描述。"""

    __tablename__ = "edit_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(80))
    original_asset_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("assets.id", ondelete="RESTRICT")
    )
    current_asset_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("assets.id", ondelete="RESTRICT")
    )
    # 采用候选或切换图片墙时递增，用于判定旧选区已失效
    revision: Mapped[int] = mapped_column(default=1)
    # 指向当前撤销位置；新操作会截断该序号之后的重做分支
    history_seq: Mapped[int] = mapped_column(default=1)
    document: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=func.now(), onupdate=func.now()
    )


class SessionAsset(Base):
    """会话图片墙。未采用的候选一并留存，切换当前图不覆盖任何已有结果。"""

    __tablename__ = "session_assets"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("edit_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    )
    # 同一事务内插入多行的时间戳相同，靠显式序号保证图片墙顺序稳定
    position: Mapped[int]
