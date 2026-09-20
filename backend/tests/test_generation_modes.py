import io
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from PIL import Image
from pydantic import ValidationError

from app.config import get_settings
from app.providers import GenerateRequest, ProviderError, get_image_provider
from app.providers.generation_modes import (
    GPT_COUNTS,
    GPT_MODES,
    GPT_RATIOS,
    generation_modes,
    gpt_model_of,
    is_gpt_mode,
    validate_generation,
)
from app.providers.l0veyou import IMAGE_HOST, L0veyouImageProvider
from app.schemas.run import GenerateIn

# 站点 /chat 公开前端固定的“模式 → 上游模型标识”映射：本次集成的唯一事实来源。
GPT_MODE_MODELS = {
    "l0veyou": "gpt-image-2",
    "l0veyou-gpt-image-2-5-flare": "gpt-image-2-5-flare",
    "l0veyou-gpt-image-2-5-full": "gpt-image-2-5-full",
}
GPT_MODE_IDS = list(GPT_MODE_MODELS)


def test_generation_defaults_to_one_image():
    assert GenerateIn(prompt="cup", provider="dashscope").count == 1


@pytest.fixture
def gpt_token(tmp_path, monkeypatch):
    path = tmp_path / "token"
    path.write_text("test-only-token")
    monkeypatch.setattr(get_settings(), "l0veyou_token_file", str(path))
    return path


def test_modes_do_not_expose_secrets(gpt_token, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "production")
    monkeypatch.setattr(get_settings(), "dashscope_api_key", "")
    modes = generation_modes()
    assert modes["default"] == "l0veyou"
    assert [item["id"] for item in modes["modes"]] == ["dashscope", *GPT_MODE_IDS]
    assert not modes["modes"][0]["enabled"]
    assert all(item["enabled"] for item in modes["modes"][1:])
    assert "test-only-token" not in json.dumps(modes)
    assert str(gpt_token) not in json.dumps(modes)


def test_modes_expose_every_confirmed_gpt_variant(gpt_token):
    by_id = {item["id"]: item for item in generation_modes()["modes"]}
    assert set(GPT_MODE_IDS) <= by_id.keys()
    for mode_id in GPT_MODE_IDS:
        mode = by_id[mode_id]
        assert mode["enabled"] is True
        assert mode["ratios"] == list(GPT_RATIOS)
        assert mode["counts"] == list(GPT_COUNTS)
    assert "GPT Image 2" in by_id["l0veyou"]["label"]
    assert "GPT Image 2.5 极速版" in by_id["l0veyou-gpt-image-2-5-flare"]["label"]
    assert "GPT Image 2.5 满血版" in by_id["l0veyou-gpt-image-2-5-full"]["label"]
    assert len(GPT_MODES) == len({mode["id"] for mode in GPT_MODES})


def test_mode_registry_maps_ids_to_fixed_upstream_models():
    assert {mode["id"] for mode in GPT_MODES} == set(GPT_MODE_IDS)
    for mode_id, model in GPT_MODE_MODELS.items():
        assert gpt_model_of(mode_id) == model
        assert is_gpt_mode(mode_id)
    # 上游 model 字符串本身不是合法模式 ID，未知模式也不被接受。
    for raw in ["gpt-image-2", "gpt-image-2-5-flare", "gpt-image-2-5-full", "invalid"]:
        assert gpt_model_of(raw) is None
        assert not is_gpt_mode(raw)


@pytest.mark.parametrize("mode_id", GPT_MODE_IDS)
def test_generate_schema_accepts_confirmed_modes(mode_id):
    assert GenerateIn(prompt="cup", provider=mode_id).provider == mode_id


@pytest.mark.parametrize(
    "value",
    ["gpt-image-2", "gpt-image-2-5-flare", "gpt-image-2-5-full", "l0veyou-gpt-image-9", "invalid"],
)
def test_generate_schema_rejects_raw_models_and_unknown_modes(value):
    with pytest.raises(ValidationError):
        GenerateIn(prompt="cup", provider=value)


@pytest.mark.parametrize("mode_id", GPT_MODE_IDS)
@pytest.mark.parametrize(
    "params",
    [
        {"count": 6},
        {"ratio": "4:5"},
        {"seed": 1},
        {"reference_asset_ids": ["some-id"]},
    ],
)
def test_gpt_modes_reject_unsupported_inputs(gpt_token, mode_id, params):
    with pytest.raises(ProviderError):
        validate_generation({"provider": mode_id, "count": 1, "ratio": "1:1", **params})


@pytest.mark.parametrize("mode_id", GPT_MODE_IDS)
def test_gpt_modes_accept_supported_params(gpt_token, mode_id):
    params = validate_generation({"provider": mode_id, "count": 2, "ratio": "9:16"})
    assert params["provider"] == mode_id
    assert params["count"] == 2


def test_unknown_gpt_mode_is_rejected(gpt_token):
    with pytest.raises(ProviderError, match="未知的生图模式"):
        validate_generation({"provider": "l0veyou-gpt-image-9", "count": 1, "ratio": "1:1"})


def test_legacy_l0veyou_keeps_original_model(gpt_token):
    params = validate_generation({"provider": "l0veyou", "count": 1, "ratio": "1:1"})
    assert params["provider"] == "l0veyou"
    assert get_image_provider("l0veyou").model == "gpt-image-2"


def test_no_fallback_for_missing_domestic_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "dashscope_api_key", "")
    with pytest.raises(ProviderError, match="API Key"):
        validate_generation({"provider": "dashscope"})


def test_explicit_provider_does_not_change_editing_default(gpt_token):
    assert get_image_provider("l0veyou").name == "l0veyou"
    assert get_image_provider().name == "mock"


async def test_gpt_submit_poll_download_original_without_credential_leak(gpt_token, monkeypatch):
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), "white").save(buffer, "PNG")
    requests = []
    callbacks = []

    def handle(request):
        requests.append(request)
        if request.url.host == IMAGE_HOST:
            assert "authorization" not in request.headers
            assert "thumbnail" not in str(request.url)
            return httpx.Response(200, content=buffer.getvalue())
        assert request.headers["authorization"] == "Bearer test-only-token"
        if request.method == "POST":
            payload = json.loads(request.content)
            assert payload["model"] == "gpt-image-2"
            assert payload["aspect_ratio"] == "1:1"
            assert "Avoid: text" in payload["prompt"]
            return httpx.Response(200, json={"data": {"id": "task-1"}})
        return httpx.Response(
            200,
            json={
                "data": {
                    "status": "completed",
                    "image_urls": [
                        f"https://{IMAGE_HOST}/image_thumbnail.webp",
                        f"https://{IMAGE_HOST}/image.png",
                    ],
                }
            },
        )

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: client_class(**kw, transport=httpx.MockTransport(handle))
    )

    async def submitted(task_id):
        callbacks.append(task_id)

    images = await L0veyouImageProvider().generate(
        GenerateRequest("cup", 1080, 1080, negative_prompt="text"), on_submitted=submitted
    )
    assert images == [buffer.getvalue()]
    assert callbacks == ["task-1"]
    assert sum(r.method == "POST" for r in requests) == 1


@pytest.mark.parametrize("mode_id, model", list(GPT_MODE_MODELS.items()))
async def test_upstream_payload_uses_mode_model(gpt_token, monkeypatch, mode_id, model):
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, "PNG")
    posted = []

    def handle(request):
        if request.url.host == IMAGE_HOST:
            assert "authorization" not in request.headers
            return httpx.Response(200, content=buffer.getvalue())
        if request.method == "POST":
            posted.append(json.loads(request.content)["model"])
            return httpx.Response(200, json={"data": {"id": "task-1"}})
        return httpx.Response(
            200,
            json={
                "data": {
                    "status": "completed",
                    "image_urls": [f"https://{IMAGE_HOST}/image.png"],
                }
            },
        )

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: client_class(**kw, transport=httpx.MockTransport(handle))
    )
    provider = get_image_provider(mode_id)
    assert provider.name == "l0veyou"
    assert provider.model == model
    images = await provider.generate(GenerateRequest("cup", 1080, 1080))
    assert images == [buffer.getvalue()]
    assert posted == [model]


@pytest.mark.parametrize("mode_id", GPT_MODE_IDS)
async def test_resume_never_resubmits_for_every_mode(gpt_token, monkeypatch, mode_id):
    methods = []

    def handle(request):
        methods.append(request.method)
        return httpx.Response(200, json={"status": "failed"})

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: client_class(**kw, transport=httpx.MockTransport(handle))
    )
    with pytest.raises(ProviderError):
        await get_image_provider(mode_id).generate(
            GenerateRequest("cup", 1080, 1080), task_id="existing"
        )
    assert methods == ["GET"]


@pytest.mark.parametrize("status, message", [(401, "过期"), (403, "拒绝"), (429, "额度")])
async def test_provider_errors_do_not_leak_response(gpt_token, monkeypatch, status, message):
    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: client_class(
            **kw,
            transport=httpx.MockTransport(
                lambda _: httpx.Response(status, json={"message": "secret-response"})
            ),
        ),
    )
    with pytest.raises(ProviderError, match=message) as exc:
        await L0veyouImageProvider().generate(GenerateRequest("cup", 1080, 1080))
    assert "secret-response" not in str(exc.value)


async def test_download_rejects_untrusted_destination():
    with pytest.raises(ProviderError):
        await L0veyouImageProvider._download("http://127.0.0.1/secrets")


async def test_resume_never_resubmits(gpt_token, monkeypatch):
    methods = []

    def handle(request):
        methods.append(request.method)
        return httpx.Response(200, json={"status": "failed"})

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: client_class(**kw, transport=httpx.MockTransport(handle))
    )
    with pytest.raises(ProviderError):
        await L0veyouImageProvider().generate(
            GenerateRequest("cup", 1080, 1080), task_id="existing"
        )
    assert methods == ["GET"]


async def test_modes_require_login(client):
    assert (await client.get("/api/generation-modes")).status_code == 401


async def test_invalid_provider_and_unavailable_mode_rejected(client, credentials, monkeypatch):
    await client.post("/api/auth/register", json=credentials)
    monkeypatch.setattr(get_settings(), "dashscope_api_key", "")
    for provider in ["invalid", "dashscope"]:
        response = await client.post(
            "/api/generations", json={"prompt": "cup", "provider": provider}
        )
        assert response.status_code == 422
    response = await client.post("/api/generations", json={"prompt": "cup", "provider": "mock"})
    assert response.status_code == 202
    assert response.json()["provider"] == "mock"


@pytest.mark.parametrize("mode_id", GPT_MODE_IDS)
@pytest.mark.parametrize("count", [1, 2, 4])
def test_gpt_batch_counts(gpt_token, mode_id, count):
    params = validate_generation({"provider": mode_id, "count": count, "ratio": "1:1"})
    assert params["count"] == count
    mode = next(mode for mode in generation_modes()["modes"] if mode["id"] == mode_id)
    assert mode["counts"] == [1, 2, 4]


@pytest.mark.parametrize("mode_id", GPT_MODE_IDS)
@pytest.mark.parametrize("count", [1, 2, 4])
async def test_gpt_batch_checkpoints_and_resume(gpt_token, monkeypatch, mode_id, count):
    from app.services import generation

    session = SimpleNamespace(commit=AsyncMock())
    run = SimpleNamespace(user_id=uuid.uuid4(), params={
        "provider": mode_id, "prompt": "cup", "ratio": "1:1", "count": count,
    })
    submitted = []

    async def generate(request, progress, *, task_id, on_submitted):
        assert request.count == 1
        assert run.params["_gpt_images"][len(submitted)]["started"]
        assert task_id is None
        submitted.append(f"task-{len(submitted)}")
        await on_submitted(submitted[-1])
        assert run.params["_gpt_images"][len(submitted) - 1]["task_id"] == submitted[-1]
        await progress(45, "working")
        return [b"image"]

    provider = SimpleNamespace(generate=AsyncMock(side_effect=generate))
    monkeypatch.setattr(generation, "get_image_provider", lambda _: provider)
    monkeypatch.setattr(generation.runs, "report", AsyncMock())
    create = AsyncMock(side_effect=lambda *args: SimpleNamespace(id=uuid.uuid4()))
    monkeypatch.setattr(generation.assets, "create_from_bytes", create)
    result = await generation.execute(session, run)
    assert len(set(result["asset_ids"])) == count
    assert provider.generate.await_count == count
    assert create.await_count == count
    assert await generation.execute(session, run) == result
    assert provider.generate.await_count == count
    values = [call.args[2] for call in generation.runs.report.await_args_list]
    assert values == sorted(values)


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("mode_id", ["l0veyou", "l0veyou-gpt-image-2-5-full"])
async def test_gpt_uncertain_submission_stops(gpt_token, monkeypatch, legacy, mode_id):
    from app.services import generation

    run = SimpleNamespace(user_id=uuid.uuid4(), params={
        "provider": mode_id, "prompt": "cup", "ratio": "1:1", "count": 2,
        **({"_submission_started": True} if legacy else {"_gpt_images": [{"started": True}]}),
    })
    provider = SimpleNamespace(generate=AsyncMock())
    monkeypatch.setattr(generation, "get_image_provider", lambda _: provider)
    with pytest.raises(ProviderError, match="重复生成"):
        await generation.execute(SimpleNamespace(commit=AsyncMock()), run)
    provider.generate.assert_not_awaited()


@pytest.mark.parametrize("mode_id", GPT_MODE_IDS)
async def test_gpt_partial_batch_resumes_existing_task(gpt_token, monkeypatch, mode_id):
    from app.services import generation

    saved = str(uuid.uuid4())
    run = SimpleNamespace(user_id=uuid.uuid4(), params={
        "provider": mode_id, "prompt": "cup", "ratio": "1:1", "count": 2,
        "_gpt_images": [{"asset_id": saved}, {"started": True, "task_id": "existing"}],
    })
    provider = SimpleNamespace(generate=AsyncMock(return_value=[b"image"]))
    monkeypatch.setattr(generation, "get_image_provider", lambda _: provider)
    monkeypatch.setattr(generation.runs, "report", AsyncMock())
    monkeypatch.setattr(generation.assets, "create_from_bytes", AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4())))
    result = await generation.execute(SimpleNamespace(commit=AsyncMock()), run)
    assert result["asset_ids"][0] == saved
    assert len(result["asset_ids"]) == 2
    assert provider.generate.await_count == 1
    assert provider.generate.await_args.kwargs["task_id"] == "existing"


@pytest.mark.parametrize("mode_id", GPT_MODE_IDS)
async def test_gpt_failure_does_not_submit_remaining_images(gpt_token, monkeypatch, mode_id):
    from app.services import generation

    run = SimpleNamespace(user_id=uuid.uuid4(), params={
        "provider": mode_id, "prompt": "cup", "ratio": "1:1", "count": 4,
    })
    provider = SimpleNamespace(generate=AsyncMock(side_effect=ProviderError("failed")))
    monkeypatch.setattr(generation, "get_image_provider", lambda _: provider)
    monkeypatch.setattr(generation.runs, "report", AsyncMock())
    with pytest.raises(ProviderError):
        await generation.execute(SimpleNamespace(commit=AsyncMock()), run)
    assert provider.generate.await_count == 1
