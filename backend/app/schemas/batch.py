import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.asset import AssetOut
from app.schemas.run import RunOut

BATCH_TOOLS = (
    "remove_background",
    "replace_background",
    "adjust_image",
    "upscale_image",
    "expand_canvas",
    "prepare_delivery_sizes",
)

MAX_BATCH_ASSETS = 20
ExportFormat = Literal["png", "jpg"]


class BatchOpIn(BaseModel):
    tool: Literal[
        "remove_background",
        "replace_background",
        "adjust_image",
        "upscale_image",
        "expand_canvas",
        "prepare_delivery_sizes",
    ]
    params: dict = Field(default_factory=dict)


class BatchIn(BaseModel):
    asset_ids: list[uuid.UUID] = Field(min_length=1, max_length=MAX_BATCH_ASSETS)
    operations: list[BatchOpIn] = Field(min_length=1, max_length=len(BATCH_TOOLS))
    formats: list[ExportFormat] = Field(default_factory=lambda: ["png"], min_length=1, max_length=2)


class BatchItemOut(BaseModel):
    source: AssetOut
    status: str
    error: str | None = None
    outputs: list[AssetOut] = []


class BatchOut(BaseModel):
    run: RunOut
    items: list[BatchItemOut] = []
    created_at: datetime
