"""对用户评测集跑确定性工具并汇总指标。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.eval.cases import Case, expect_size_of, load_cases
from app.eval.metrics import alpha_iou, contain, image_size, mae, passes, psnr, size_score
from app.eval.tasks import run_task

DEFAULT_THRESHOLDS = {
    "alpha_iou": 0.8,
    "mae": 12.0,
    "psnr": 20.0,
    "contain": 0.99,
    "size": 1.0,
}

_SCORERS = {
    "mae": lambda pred, expect, source: mae(pred, expect),
    "psnr": lambda pred, expect, source: psnr(pred, expect),
    "alpha_iou": lambda pred, expect, source: alpha_iou(pred, expect),
    "contain": lambda pred, expect, source: contain(source, pred),
}


@dataclass
class OutputScore:
    label: str
    values: dict[str, float]
    ok: bool


@dataclass
class CaseResult:
    case: Case
    outputs: list[OutputScore] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and all(item.ok for item in self.outputs)


def _score_output(
    case: Case, label: str, pred: bytes, source: bytes, expect: bytes | None
) -> OutputScore:
    values: dict[str, float] = {}
    ok = True
    for name in case.metrics:
        if name == "size":
            size = expect_size_of(case, label)
            if size is None and expect is not None:
                size = image_size(expect)
            if size is None:
                raise ValueError(f"{case.id} 的 size 指标需要 expect 图或目标宽高")
            values[name] = size_score(pred, *size)
        elif name in _SCORERS:
            if name != "contain" and expect is None:
                raise ValueError(f"{case.id} 的 {name} 需要 expect")
            values[name] = _SCORERS[name](pred, expect or b"", source)
        else:
            raise ValueError(f"未知指标：{name}")
        threshold = case.thresholds.get(name, DEFAULT_THRESHOLDS[name])
        ok = ok and passes(name, values[name], threshold)
    return OutputScore(label=label, values=values, ok=ok)


def _read(path: Path) -> bytes:
    if not path.is_file():
        raise FileNotFoundError(f"缺少文件：{path}")
    return path.read_bytes()


def evaluate_case(root: Path, case: Case) -> CaseResult:
    try:
        source = _read(case.input_path(root))
        produced = run_task(case.task, source, case.params)
        expect_file = case.expect_path(root)
        if expect_file and expect_file.is_dir():
            scores = [
                _score_output(case, label, pred, source, _read(expect_file / f"{label}.png"))
                for label, pred in produced
            ]
            return CaseResult(case=case, outputs=scores)
        expect = _read(expect_file) if expect_file else None
        return CaseResult(
            case=case,
            outputs=[_score_output(case, label, pred, source, expect) for label, pred in produced],
        )
    except Exception as exc:
        return CaseResult(case=case, error=str(exc))


def evaluate(root: Path) -> list[CaseResult]:
    return [evaluate_case(root, case) for case in load_cases(root)]


def render(results: list[CaseResult]) -> str:
    names = []
    for result in results:
        names.extend(result.case.metrics)
    columns = list(dict.fromkeys(names))
    header = ["id", "task", *columns, "result"]
    rows = [header]
    for result in results:
        if result.error:
            rows.append([result.case.id, result.case.task, *["—"] * len(columns), result.error])
            continue
        for item in result.outputs:
            mark = "ok" if item.ok else "fail"
            cells = [_fmt(item.values.get(name)) for name in columns]
            suffix = "" if item.label == result.case.task else f"/{item.label}"
            label = f"{result.case.id}{suffix}"
            rows.append([label, result.case.task, *cells, mark])
    widths = [max(len(row[i]) for row in rows) for i in range(len(header))]
    lines = ["  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in rows]
    passed = sum(1 for result in results if result.ok)
    lines.append(f"{passed}/{len(results)} passed")
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.4f}".rstrip("0").rstrip(".")
