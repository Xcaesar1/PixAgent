from pathlib import Path

from app.config import get_settings
from app.providers.base import ProviderError

GPT_RATIOS = ("1:1", "3:4", "9:16", "16:9")
GPT_COUNTS = (1, 2, 4)

# 上游站点 /chat 前端固化的模型标识（来源：站点公开前端资源 DoubaoView）。
# 浏览器只提交下面的模式 ID，上游 model 字符串始终由服务端映射，避免任意模型注入。
# "l0veyou" 是历史模式 ID，保留用于兼容已持久化的任务，固定对应 GPT Image 2。
GPT_MODES = (
    {"id": "l0veyou", "model": "gpt-image-2", "label": "GPT 生图 · GPT Image 2"},
    {
        "id": "l0veyou-gpt-image-2-5-flare",
        "model": "gpt-image-2-5-flare",
        "label": "GPT 生图 · GPT Image 2.5 极速版",
    },
    {
        "id": "l0veyou-gpt-image-2-5-full",
        "model": "gpt-image-2-5-full",
        "label": "GPT 生图 · GPT Image 2.5 满血版",
    },
)


def gpt_model_of(name: str) -> str | None:
    """把模式 ID 映射为固定的上游模型标识；未知模式返回 None。"""
    return next((mode["model"] for mode in GPT_MODES if mode["id"] == name), None)


def is_gpt_mode(name: str) -> bool:
    return gpt_model_of(name) is not None


def gpt_ready() -> bool:
    settings = get_settings()
    try:
        return bool(settings.l0veyou_token_file) and bool(
            Path(settings.l0veyou_token_file).read_text().strip()
        )
    except OSError:
        return False


def generation_modes() -> dict:
    settings = get_settings()
    ready = gpt_ready()
    gpt_description = (
        "多张依次生成；使用站点账号额度；登录过期需更新凭证" if ready else "未配置登录凭证"
    )
    modes = [
        {
            "id": "dashscope",
            "label": "国内生图 · 通义千问",
            "enabled": bool(settings.dashscope_api_key),
            "description": "按 DashScope 账户计费"
            if settings.dashscope_api_key
            else "未配置 API Key",
            "ratios": ["1:1", "4:5", "3:4", "9:16", "16:9"],
            "counts": [1, 2, 4, 6],
        },
        *[
            {
                "id": mode["id"],
                "label": mode["label"],
                "enabled": ready,
                "description": gpt_description,
                "ratios": list(GPT_RATIOS),
                "counts": list(GPT_COUNTS),
            }
            for mode in GPT_MODES
        ],
    ]
    if not settings.is_production and settings.image_provider == "mock":
        modes.append(
            {
                "id": "mock",
                "label": "测试占位图",
                "enabled": True,
                "description": "仅用于测试，不调用模型",
                "ratios": ["1:1", "4:5", "3:4", "9:16", "16:9"],
                "counts": [1, 2, 4, 6],
            }
        )
    preferred = settings.generation_provider or settings.image_provider
    enabled = [mode["id"] for mode in modes if mode["enabled"]]
    return {
        "modes": modes,
        "default": preferred if preferred in enabled else next(iter(enabled), None),
    }


def validate_generation(params: dict) -> dict:
    settings = get_settings()
    name = params.get("provider") or settings.generation_provider or settings.image_provider
    if name == "dashscope":
        if not settings.dashscope_api_key:
            raise ProviderError("国内生图尚未配置 API Key，请联系管理员")
    elif is_gpt_mode(name):
        if not gpt_ready():
            raise ProviderError("GPT 生图尚未配置登录凭证，请联系管理员")
        if params.get("count", 1) not in GPT_COUNTS:
            raise ProviderError("GPT 生图支持 1、2、4 张，多张将依次生成")
        if params.get("ratio", "1:1") not in GPT_RATIOS:
            raise ProviderError("GPT 生图暂不支持该比例，请选择 1:1、3:4、9:16 或 16:9")
        if params.get("reference_asset_ids") or params.get("seed") is not None:
            raise ProviderError("GPT 模式当前仅支持文生图，不支持参考图或随机种子")
    elif name != "mock":
        raise ProviderError("未知的生图模式")
    return {**params, "provider": name}
