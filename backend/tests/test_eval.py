import io
import json
from pathlib import Path

from PIL import Image, ImageDraw

from app.config import get_settings
from app.eval import evaluate, render
from app.eval.__main__ import main
from app.eval.metrics import alpha_iou, contain, mae, passes, psnr, size_score
from app.eval.tasks import run_task
from app.storage import _client, signed_url


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _subject(size=(200, 120)) -> bytes:
    image = Image.new("RGB", size, (240, 240, 240))
    ImageDraw.Draw(image).ellipse((40, 20, 160, 100), fill=(20, 80, 180))
    return _png(image)


def test_mae_and_psnr_match_identical_images():
    data = _subject()
    assert mae(data, data) == 0
    assert psnr(data, data) == 99


def test_alpha_iou_on_known_masks():
    pred = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    expect = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    for x in range(6):
        for y in range(6):
            pred.putpixel((x, y), (255, 0, 0, 255))
    for x in range(4, 10):
        for y in range(4, 10):
            expect.putpixel((x, y), (0, 255, 0, 255))

    score = alpha_iou(_png(pred), _png(expect))
    assert abs(score - 4 / 68) < 1e-6


def test_letterbox_keeps_subject_inside_frame():
    source = _subject()
    _, output = run_task("letterbox", source, {"width": 1080, "height": 1920})[0]
    assert size_score(output, 1080, 1920) == 1
    assert contain(source, output) == 1


def test_delivery_sizes_match_ratios():
    outputs = run_task("prepare_delivery_sizes", _subject(), {"ratios": ["1:1", "9:16"]})
    assert [label for label, _ in outputs] == ["1:1", "9:16"]
    assert size_score(outputs[0][1], 1080, 1080) == 1
    assert size_score(outputs[1][1], 1080, 1920) == 1


def test_threshold_direction():
    assert passes("mae", 3, 12)
    assert not passes("mae", 13, 12)
    assert passes("alpha_iou", 0.9, 0.8)
    assert not passes("alpha_iou", 0.5, 0.8)


def test_evaluate_user_dataset(tmp_path: Path):
    source = _subject()
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.png").write_bytes(source)
    (tmp_path / "cases.json").write_text(
        json.dumps(
            [
                {
                    "id": "delivery",
                    "task": "prepare_delivery_sizes",
                    "input": "images/a.png",
                    "params": {"ratios": ["1:1"]},
                    "metrics": ["size", "contain"],
                },
                {
                    "id": "adjust",
                    "task": "adjust_image",
                    "input": "images/a.png",
                    "expect": "images/a.png",
                    "params": {},
                    "metrics": ["mae"],
                },
            ]
        ),
        encoding="utf-8",
    )

    results = evaluate(tmp_path)
    assert all(result.ok for result in results)
    table = render(results)
    assert "2/2 passed" in table
    assert main([str(tmp_path)]) == 0


def test_evaluate_reports_missing_cases(tmp_path: Path, capsys):
    assert main([str(tmp_path)]) == 2
    assert "cases.json" in capsys.readouterr().err


def test_signed_url_uses_public_endpoint():
    settings = get_settings()
    original = settings.s3_public_endpoint
    settings.s3_public_endpoint = "http://localhost:7313"
    _client.cache_clear()
    try:
        url = signed_url("eval/demo.png")
        assert url.startswith("http://localhost:7313/")
        assert "X-Amz-Signature" in url
    finally:
        settings.s3_public_endpoint = original
        _client.cache_clear()
