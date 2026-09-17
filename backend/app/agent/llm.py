from functools import lru_cache

from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.tools import SPECS, ToolSpec

# 图像模型必须走 DashScope 原生接口，纯文本的规划模型可用 OpenAI 兼容模式
_COMPATIBLE_PATH = "/compatible-mode/v1"


class PlannerUnavailable(Exception):
    """规划模型未配置或不可用。"""


def _schema_of(spec: ToolSpec) -> dict:
    function = convert_to_openai_function(spec.params)
    function["name"] = spec.name
    function["description"] = spec.description

    parameters = function.get("parameters", {})
    for hidden in spec.agent_hidden:
        parameters.get("properties", {}).pop(hidden, None)
    parameters["required"] = [
        name for name in parameters.get("required", []) if name not in spec.agent_hidden
    ]
    return {"type": "function", "function": function}


@lru_cache
def planner():
    """绑定全部已注册工具的规划模型。工具增减无需改动此处。"""
    settings = get_settings()
    if not settings.dashscope_api_key:
        raise PlannerUnavailable("未配置 DASHSCOPE_API_KEY，对话指令不可用")

    model = ChatOpenAI(
        model=settings.planner_model,
        api_key=settings.dashscope_api_key,
        base_url=f"{settings.dashscope_base_url}{_COMPATIBLE_PATH}",
        temperature=0,
    )
    return model.bind_tools([_schema_of(spec) for spec in SPECS])
