from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ToolRun

ToolHandler = Callable[[AsyncSession, ToolRun], Awaitable[dict]]

# 遮罩由服务端从当轮选区填入，模型只管点名图层
HIDDEN_MASK = ("mask_asset_id", "revision")


class UnknownTool(Exception):
    pass


class LayerRef(BaseModel):
    """改哪一层。与选区正交：选区限定区域，layer_id 限定图层。"""

    layer_id: str | None = Field(
        default=None,
        description=(
            "要修改的图层 id 或名字，如 background、subject、物体2。"
            "不填则作用在选区下最上层可见图像。"
        ),
    )


class MaskRef(BaseModel):
    """改哪块区域。两个字段都由服务端填入，不暴露给模型。"""

    mask_asset_id: str | None = None
    revision: int | None = None


@dataclass(frozen=True)
class ToolSpec:
    """一个工具的完整定义，界面与 Agent 共用。

    params 同时用于服务端校验和生成模型的函数签名，两者不会漂移。
    handler 只关心业务结果，状态流转由统一的执行外壳负责。
    """

    name: str
    label: str
    description: str
    params: type[BaseModel]
    handler: ToolHandler
    needs_approval: bool = False
    # 只改 LayerDocument 的工具当场执行；像素工具仍走队列
    queued: bool = True
    session_required: bool = False
    # 素材 ID、随机种子这类参数应由服务端从上下文填入，不暴露给模型
    agent_hidden: tuple[str, ...] = field(default_factory=tuple)
    # 同一工具按参数细分说法，例如翻转要分水平与垂直，返回 None 则用 label
    detail: Callable[[dict], str | None] | None = None

    def label_for(self, params: dict | None = None) -> str:
        refined = self.detail(params or {}) if self.detail else None
        return refined or self.label
