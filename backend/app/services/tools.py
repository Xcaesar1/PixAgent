import logging
import uuid

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.layers import LayerDocument
from app.models import Asset, ToolRun
from app.models.tool_run import RunStatus
from app.providers import ProviderError
from app.providers.generation_modes import validate_generation
from app.queue import enqueue
from app.services import assets, runs, sessions
from app.tools import UnknownTool, spec_of
from app.tools.context import ToolError

TASK = "run_tool"

logger = logging.getLogger(__name__)


class InvalidParams(Exception):
    pass


def validate(tool: str, params: dict) -> dict:
    """按工具自己的模型校验参数，界面与 Agent 走同一套规则。"""
    spec = spec_of(tool)
    try:
        return spec.params.model_validate(params).model_dump(mode="json")
    except ValidationError as exc:
        raise InvalidParams(_first_error(exc)) from exc


async def submit(
    session: AsyncSession,
    user_id: uuid.UUID,
    tool: str,
    params: dict,
    session_id: uuid.UUID | None = None,
) -> ToolRun:
    spec = spec_of(tool)
    if spec.session_required and session_id is None:
        raise InvalidParams("此工具需要在编辑会话中使用")

    validated = validate(tool, params)
    if tool == "generate_image":
        try:
            validated = validate_generation(validated)
        except ProviderError as exc:
            raise InvalidParams(str(exc)) from exc
    run = await runs.create(session, user_id, tool, validated, session_id)
    if spec.queued:
        await enqueue(TASK, run.id)
    else:
        await execute(session, run)
        await session.refresh(run)
    return run


async def execute(session: AsyncSession, run: ToolRun) -> None:
    """统一的执行外壳：状态流转与失败兜底集中在此，具体工具只返回结果。"""
    try:
        spec = spec_of(run.tool)
        await runs.start(session, run)
        result = await spec.handler(session, run)
        await _record(session, run, result)
    except (ProviderError, UnknownTool, ToolError) as exc:
        await runs.finish(session, run, status=RunStatus.FAILED, error=str(exc))
    except Exception:
        logger.exception("工具执行异常 tool=%s run_id=%s", run.tool, run.id)
        await session.rollback()
        await runs.finish(session, run, status=RunStatus.FAILED, error="执行失败，请重试")
    else:
        await runs.finish(session, run, status=RunStatus.SUCCEEDED, result=result)

    from app.services import agent as agent_service

    await agent_service.continue_plan(session, run)


async def _record(session: AsyncSession, run: ToolRun, result: dict) -> None:
    if run.session_id is None:
        return

    try:
        record = await sessions.load(session, run.session_id)
    except sessions.SessionNotFound:
        return

    produced = await _assets(session, run.user_id, result.get("asset_ids", []))
    adopt_id = result.get("adopt_asset_id")
    current = next((asset for asset in produced if str(asset.id) == adopt_id), None)
    raw_document = result.get("document")
    document = LayerDocument.model_validate(raw_document) if raw_document else None

    if document is not None or current is not None:
        await sessions.apply_edit(
            session,
            record,
            run.tool,
            params=run.params,
            document=document,
            current=current,
            extra_assets=produced,
            result=result,
        )
        return

    if produced:
        await sessions.record_result(session, record, produced, run.tool, run.params, result)


async def _assets(session: AsyncSession, user_id: uuid.UUID, ids: list) -> list[Asset]:
    result: list[Asset] = []
    for raw in ids:
        asset = await assets.get_for_user(session, user_id, uuid.UUID(raw))
        if asset is not None:
            result.append(asset)
    return result


def _first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    field = ".".join(str(part) for part in error["loc"]) or "参数"
    return f"{field}：{error['msg']}"
