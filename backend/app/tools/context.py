import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app import storage
from app.edits.render import WHITE, flatten
from app.layers import LayerDocument
from app.models import EditSession, ToolRun
from app.services import assets, sessions


class ToolError(Exception):
    """可直接展示给用户的工具失败。"""


async def require_session(session: AsyncSession, run: ToolRun) -> EditSession:
    if run.session_id is None:
        raise ToolError("此工具需要在编辑会话中使用")
    try:
        return await sessions.load(session, run.session_id)
    except sessions.SessionNotFound as exc:
        raise ToolError("会话不存在") from exc


def document_of(record: EditSession) -> LayerDocument:
    return LayerDocument.model_validate(record.document)


async def flatten_session(
    session: AsyncSession,
    record: EditSession,
    *,
    background: tuple[int, int, int, int] = WHITE,
    include_text: bool = True,
) -> bytes:
    """把当前文档拍平为 PNG，再交给像素工具。"""
    document = document_of(record)
    images: dict[uuid.UUID, bytes] = {}
    for layer in document.layers:
        if layer.asset_id is None:
            continue
        asset = await assets.get_for_user(session, record.user_id, layer.asset_id)
        if asset is None:
            continue
        images[asset.id] = await storage.get(asset.storage_key)
    return flatten(document, images, background=background, include_text=include_text)
