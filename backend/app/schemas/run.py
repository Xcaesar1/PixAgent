import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from app.models.tool_run import RunStatus, ToolRun
from app.ratios import Ratio
from app.schemas.asset import AssetOut

MAX_PROMPT = 1500
MAX_REFERENCES = 3


class GenerateIn(BaseModel):
    # 模式 ID 白名单，与 app.providers.generation_modes.GPT_MODES 保持一致；
    # 上游 model 字符串不接受浏览器输入。
    provider: Literal[
        "dashscope",
        "l0veyou",
        "l0veyou-gpt-image-2-5-flare",
        "l0veyou-gpt-image-2-5-full",
        "mock",
    ] | None = None
    prompt: Annotated[str, Field(min_length=1, max_length=MAX_PROMPT)]
    ratio: Ratio = Ratio.SQUARE
    count: Annotated[int, Field(ge=1, le=6)] = 1
    negative_prompt: Annotated[str | None, Field(max_length=MAX_PROMPT)] = None
    seed: Annotated[int | None, Field(ge=0, le=2147483647)] = None
    reference_asset_ids: Annotated[list[uuid.UUID], Field(max_length=MAX_REFERENCES)] = []

    @field_validator("prompt")
    @classmethod
    def _require_prompt(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("提示词不能为空")
        return value

    @field_validator("negative_prompt")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value else None


class RunOut(BaseModel):
    id: uuid.UUID
    tool: str
    status: RunStatus
    progress: int
    stage: str
    error: str | None
    prompt: str | None = None
    provider: str | None = None
    candidates: list[AssetOut] = []
    result: dict = {}

    @classmethod
    def of(cls, run: ToolRun, candidates: list[AssetOut] | None = None) -> "RunOut":
        return cls(
            id=run.id,
            tool=run.tool,
            status=run.status,
            progress=run.progress,
            stage=run.stage,
            error=run.error,
            prompt=run.params.get("prompt"),
            provider=run.params.get("provider"),
            candidates=candidates or [],
            result=run.result or {},
        )
