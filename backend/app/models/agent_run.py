import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase, enum_column
from app.models.tool_run import RunStatus


class AgentRun(UUIDBase):
    """一轮自然语言指令的规划与执行进度，对应编辑页左栏的一次问答。

    plan 即断点：刷新或 worker 重启后按已落库的步骤状态继续。
    """

    __tablename__ = "agent_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("edit_sessions.id", ondelete="CASCADE"), index=True
    )
    # 规划所基于的修订号，用于判断执行时画布是否已被改动
    revision: Mapped[int]
    goal: Mapped[str] = mapped_column(Text)
    reply: Mapped[str] = mapped_column(Text, default="")
    plan: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[RunStatus] = mapped_column(enum_column(RunStatus))
    error: Mapped[str | None] = mapped_column(Text, default=None)
