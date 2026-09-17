from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase


class User(UUIDBase):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
