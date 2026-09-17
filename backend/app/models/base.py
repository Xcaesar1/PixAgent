import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

ENUM_LENGTH = 16

# 全库时间统一带时区存储，避免跨时区读写产生歧义
TIMESTAMPTZ = DateTime(timezone=True)


def enum_column(enum_cls: type[enum.Enum]) -> Enum:
    """以 VARCHAR 存枚举值本身，读取时还原为枚举成员。

    不使用 PostgreSQL 原生枚举，增删取值无需 ALTER TYPE。
    """
    return Enum(
        enum_cls,
        native_enum=False,
        create_constraint=False,
        values_callable=lambda cls: [member.value for member in cls],
        length=ENUM_LENGTH,
    )


class UUIDBase(Base):
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now())
