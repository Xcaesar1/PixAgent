from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.eval.runner import evaluate, render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="对用户提供的评测集计算指标")
    parser.add_argument("dataset", type=Path, help="含 cases.json 与素材的目录")
    args = parser.parse_args(argv)
    root = args.dataset.expanduser().resolve()
    try:
        results = evaluate(root)
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        print("可直接跑自带评测集：uv run python -m app.eval app/eval/dataset", file=sys.stderr)
        return 2
    print(render(results))
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
