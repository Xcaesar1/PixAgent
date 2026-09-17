from app.schemas.run import GenerateIn
from app.services import generation
from app.tools.base import ToolSpec

GENERATE_IMAGE = ToolSpec(
    name="generate_image",
    label="生成图片",
    description=(
        "根据文字描述从零生成图片候选。没有可编辑的图片，"
        "或用户明确要求换一张全新画面时使用；修改现有图片不要用它。"
    ),
    params=GenerateIn,
    handler=generation.execute,
    agent_hidden=("seed", "reference_asset_ids"),
)
