"""读取用户提供的 cases.json。"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from app.eval.tasks import TASKS
from app.ratios import Ratio, size_of


class Case(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    task: str
    input: str
    expect: str | None = None
    params: dict = Field(default_factory=dict)
    metrics: list[str] = Field(min_length=1)
    thresholds: dict[str, float] = Field(default_factory=dict)

    def input_path(self, root: Path) -> Path:
        return (root / self.input).resolve()

    def expect_path(self, root: Path) -> Path | None:
        return (root / self.expect).resolve() if self.expect else None


def load_cases(root: Path) -> list[Case]:
    path = root / "cases.json"
    if not path.is_file():
        raise FileNotFoundError(f"未找到 {path}，可参考 app/eval/dataset 或 cases.example.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("cases.json 须为非空数组")
    cases = [Case.model_validate(item) for item in raw]
    unknown = sorted({case.task for case in cases if case.task not in TASKS})
    if unknown:
        raise ValueError(f"未知任务：{', '.join(unknown)}")
    return cases


def expect_size_of(case: Case, label: str) -> tuple[int, int] | None:
    if case.task == "letterbox":
        return int(case.params["width"]), int(case.params["height"])
    if case.task == "resize":
        return int(case.params["width"]), int(case.params["height"])
    if case.task == "prepare_delivery_sizes":
        return size_of(Ratio(label))
    return None
