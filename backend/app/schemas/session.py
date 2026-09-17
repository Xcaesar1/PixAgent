import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.layers import LayerDocument
from app.models import EditHistory, EditSession
from app.schemas.asset import AssetOut
from app.schemas.run import RunOut

MAX_WALL_ASSETS = 12


class SessionCreateIn(BaseModel):
    current_asset_id: uuid.UUID
    # 同批未采用的候选一并进图片墙
    asset_ids: Annotated[list[uuid.UUID], Field(max_length=MAX_WALL_ASSETS)] = []
    title: str | None = None


class SessionPatchIn(BaseModel):
    title: str | None = None
    current_asset_id: uuid.UUID | None = None


class ToolInvokeIn(BaseModel):
    tool: str
    params: dict = {}


class PointIn(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class SelectIn(BaseModel):
    revision: int
    points: list[PointIn] = []
    strokes: list[list[PointIn]] = []
    radius: float = Field(default=0.03, ge=0.005, le=0.12)
    append: bool = False


class MarkerOut(BaseModel):
    index: int
    x: float
    y: float


class SelectionOut(BaseModel):
    revision: int
    mask: AssetOut
    markers: list[MarkerOut] = []


class SessionOut(BaseModel):
    id: uuid.UUID
    title: str
    revision: int
    history_seq: int
    original_asset_id: uuid.UUID
    current_asset_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, record: EditSession) -> "SessionOut":
        return cls(
            id=record.id,
            title=record.title,
            revision=record.revision,
            history_seq=record.history_seq,
            original_asset_id=record.original_asset_id,
            current_asset_id=record.current_asset_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class SessionDetailOut(SessionOut):
    document: LayerDocument
    previous_document: LayerDocument | None = None
    assets: list[AssetOut] = []
    can_undo: bool = False
    can_redo: bool = False

    @classmethod
    def of_detail(
        cls,
        record: EditSession,
        assets: list[AssetOut],
        *,
        previous_document: LayerDocument | None = None,
        can_undo: bool = False,
        can_redo: bool = False,
    ) -> "SessionDetailOut":
        return cls(
            **SessionOut.of(record).model_dump(),
            document=LayerDocument.model_validate(record.document),
            previous_document=previous_document,
            assets=assets,
            can_undo=can_undo,
            can_redo=can_redo,
        )


class ToolInvokeOut(BaseModel):
    run: RunOut
    session: SessionDetailOut


class HistoryOut(BaseModel):
    seq: int
    action: str
    params: dict
    result: dict
    created_at: datetime

    @classmethod
    def of(cls, entry: EditHistory) -> "HistoryOut":
        return cls(
            seq=entry.seq,
            action=entry.action,
            params=entry.params,
            result=entry.result,
            created_at=entry.created_at,
        )
