import uuid
from io import BytesIO

import pytest
from PIL import Image

from app.edits.document import (
    EditError,
    crop,
    flip,
    move,
    reorder,
    rotate,
    scale,
    set_opacity,
    set_text,
    set_visible,
)
from app.edits.mask import apply_masked, overlay_png, rasterize_strokes, to_luma
from app.edits.ocr import TextBox
from app.edits.pixels import adjust, remove_background
from app.edits.render import TRANSPARENT, flatten
from app.edits.segment import _circles
from app.edits.split import (
    already_promoted,
    already_split,
    cut_object,
    fill_background,
    mask_hash,
    punch,
    remove_text,
    split_document,
    text_mask,
)
from app.layers import (
    BACKGROUND_LAYER_ID,
    BASE_LAYER_ID,
    SUBJECT_LAYER_ID,
    Layer,
    LayerDocument,
    LayerKind,
    LayerMissing,
    Transform,
)
from app.providers.dashscope import _fit_edit_size
from app.ratios import Ratio, cover_size


def _doc(width=400, height=500, **transform) -> LayerDocument:
    return LayerDocument(
        width=width,
        height=height,
        layers=[
            Layer(
                id=BASE_LAYER_ID,
                kind=LayerKind.IMAGE,
                name="底图",
                width=width,
                height=height,
                transform=Transform(**transform),
            )
        ],
    )


def test_flip_negates_scale_in_place():
    flipped = flip(_doc(), None, "horizontal")

    assert flipped.layers[0].transform.scale_x == -1
    assert flipped.layers[0].transform.x == 0


def test_scale_factor_keeps_flip_direction():
    flipped = flip(_doc(), None, "horizontal")

    scaled = scale(flipped, None, factor=0.5)

    assert scaled.layers[0].transform.scale_x == -0.5
    assert scaled.layers[0].transform.scale_y == 0.5


def test_absolute_scale_preserves_sign():
    flipped = flip(_doc(), None, "vertical")

    scaled = scale(flipped, None, scale_y=2)

    assert scaled.layers[0].transform.scale_y == -2


def test_scale_writes_position_alongside_the_factor():
    """拖角缩放会挪动中心，位置与倍率同一次写入才能一起撤销。"""
    scaled = scale(_doc(400, 500), None, scale_x=2, scale_y=2, x=-100, y=-125)

    transform = scaled.layers[0].transform
    assert (transform.scale_x, transform.scale_y) == (2, 2)
    assert (transform.x, transform.y) == (-100, -125)


def test_rotate_can_be_relative_or_absolute():
    turned = rotate(_doc(), None, angle=8)
    assert turned.layers[0].transform.rotation == 8

    reset = rotate(turned, None, rotation=-15)
    assert reset.layers[0].transform.rotation == -15


def test_opacity_is_absolute():
    assert set_opacity(_doc(), None, 0.4).layers[0].opacity == 0.4


def test_visible_is_absolute():
    hidden = set_visible(_doc(), "base", False)
    assert hidden.layers[0].visible is False
    assert set_visible(hidden, "base", True).layers[0].visible is True


def test_move_accepts_absolute_and_relative():
    shifted = move(_doc(), None, dx=12, dy=-8)
    assert (shifted.layers[0].transform.x, shifted.layers[0].transform.y) == (12, -8)

    parked = move(shifted, None, x=3, y=4)
    assert (parked.layers[0].transform.x, parked.layers[0].transform.y) == (3, 4)


def test_reorder_moves_named_layer_to_top():
    document = LayerDocument(
        width=100,
        height=100,
        layers=[
            Layer(id="a", kind=LayerKind.IMAGE, name="A", width=100, height=100),
            Layer(id="b", kind=LayerKind.IMAGE, name="B", width=100, height=100),
        ],
    )

    assert [layer.id for layer in reorder(document, "a", "top").layers] == ["b", "a"]
    assert [layer.id for layer in reorder(document, "b", "down").layers] == ["b", "a"]


def test_crop_to_ratio_is_centered():
    cropped = crop(_doc(400, 500), ratio=Ratio.SQUARE)

    assert (cropped.width, cropped.height) == (400, 400)
    assert cropped.layers[0].transform.y == -50


def test_crop_normalized_rect_shifts_layers():
    cropped = crop(_doc(200, 200), rect=(0.25, 0.25, 0.5, 0.5))

    assert (cropped.width, cropped.height) == (100, 100)
    assert (cropped.layers[0].transform.x, cropped.layers[0].transform.y) == (-50, -50)


def _png(color, size=(80, 80), box=None) -> bytes:
    image = Image.new("RGBA", size, color)
    if box:
        Image.Image.paste(
            image,
            Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), (200, 30, 30, 255)),
            box[:2],
        )
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_flatten_clips_to_canvas_and_honors_opacity():
    asset_id = uuid.uuid4()
    document = crop(_doc(80, 80), rect=(0.25, 0.25, 0.5, 0.5))
    document.layers[0].asset_id = asset_id
    document.layers[0].opacity = 0.5
    raw = _png((10, 80, 200, 255), (80, 80))

    flat = Image.open(BytesIO(flatten(document, {asset_id: raw})))

    assert flat.size == (40, 40)
    # 半透明叠在白底上，通道应介于原色与 255 之间
    assert 10 < flat.getpixel((20, 20))[0] < 255


def test_remove_background_clears_corner_color():
    data = _png((255, 255, 255, 255), (64, 64), box=(16, 16, 48, 48))

    result = Image.open(BytesIO(remove_background(data)))

    assert result.getpixel((2, 2))[3] == 0
    assert result.getpixel((32, 32))[3] == 255


def test_adjust_brightness_lightens_pixels():
    data = _png((80, 80, 80, 255), (48, 48))
    bright = Image.open(BytesIO(adjust(data, brightness=0.4)))

    assert bright.getpixel((8, 8))[0] > 80


def test_adjust_preserves_transparent_pixels():
    data = _png((0, 0, 0, 0), (64, 64), box=(16, 16, 48, 48))
    result = Image.open(BytesIO(adjust(data, brightness=-0.7, contrast=-0.6)))

    assert result.getpixel((2, 2))[3] == 0
    assert result.getpixel((32, 32))[3] == 255
    assert result.getpixel((32, 32))[0] > 0


def test_adjust_vignette_darkens_corners():
    data = _png((200, 180, 160, 255), (64, 64))
    result = Image.open(BytesIO(adjust(data, vignette=0.8)))

    assert result.getpixel((2, 2))[0] < result.getpixel((32, 32))[0]


def test_masked_composite_keeps_pixels_outside_the_selection():
    source = _png((10, 20, 30, 255), (48, 48))
    edited = _png((200, 10, 10, 255), (48, 48))
    mask = Image.new("L", (48, 48), 0)
    mask.paste(255, (0, 0, 12, 12))

    result = Image.open(BytesIO(apply_masked(source, edited, overlay_png(mask))))

    assert result.getpixel((6, 6))[:3] == (200, 10, 10)
    assert result.getpixel((40, 40))[:3] == (10, 20, 30)


def test_cut_object_keeps_only_masked_pixels():
    source = _png((10, 20, 30, 255), (48, 48))
    mask = Image.new("L", (48, 48), 0)
    mask.paste(255, (8, 8, 20, 20))

    cut, x, y, width, height = cut_object(source, overlay_png(mask))
    result = Image.open(BytesIO(cut))

    assert (x, y, width, height) == (8, 8, 12, 12)
    assert result.getpixel((2, 2))[:3] == (10, 20, 30)
    assert result.getpixel((2, 2))[3] == 255


def test_fill_background_replaces_masked_subject():
    from PIL import ImageDraw

    image = Image.new("RGB", (80, 80), (220, 200, 180))
    ImageDraw.Draw(image).ellipse((20, 20, 60, 60), fill=(20, 80, 200))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    mask = Image.new("L", (80, 80), 0)
    mask.paste(255, (18, 18, 62, 62))

    result = Image.open(BytesIO(fill_background(buffer.getvalue(), overlay_png(mask))))
    center = result.getpixel((40, 40))[:3]

    assert center != (20, 80, 200)
    assert abs(center[0] - 220) < abs(center[0] - 20)
    assert result.getpixel((4, 4))[:3] == (220, 200, 180)


def test_punch_clears_masked_pixels_and_keeps_the_rest():
    source = _png((10, 20, 30, 255), (48, 48))
    mask = Image.new("L", (48, 48), 0)
    mask.paste(255, (0, 0, 12, 12))

    result = Image.open(BytesIO(punch(source, overlay_png(mask))))

    assert result.getpixel((4, 4))[3] == 0
    assert result.getpixel((40, 40))[:3] == (10, 20, 30)


def test_text_mask_covers_boxes():
    luma = to_luma(text_mask((40, 30), [TextBox("A", 4, 6, 10, 8)], grow=0))

    assert luma.getpixel((8, 10)) == 255
    assert luma.getpixel((0, 0)) == 0


def test_remove_text_punches_subject_and_keeps_background_opaque():
    size = (48, 48)
    next_subject, next_bg = remove_text(
        _png((10, 20, 30, 255), size),
        _png((200, 180, 40, 255), size),
        [TextBox("A", 0, 0, 12, 12)],
        size,
    )

    punched = Image.open(BytesIO(next_subject))
    filled = Image.open(BytesIO(next_bg))
    assert punched.getpixel((4, 4))[3] == 0
    assert punched.getpixel((40, 40))[:3] == (10, 20, 30)
    assert filled.getpixel((4, 4))[3] == 255
    assert filled.getpixel((40, 40))[:3] == (200, 180, 40)


def _text_doc() -> LayerDocument:
    return LayerDocument(
        width=80,
        height=60,
        layers=[
            Layer(id=BASE_LAYER_ID, kind=LayerKind.IMAGE, name="底图", width=80, height=60),
            Layer(
                id="text-1",
                kind=LayerKind.TEXT,
                name="夏日",
                width=40,
                height=16,
                text="夏日",
                font_size=14,
                fill="#141414",
            ),
        ],
    )


def test_set_text_updates_copy_and_name():
    document = _text_doc()

    updated = set_text(document, "text-1", "新品上市", font_size=18, fill="#ff0000")
    layer = updated.layers[-1]

    assert layer.text == "新品上市"
    assert layer.name == "新品上市"
    assert layer.font_size == 18
    assert layer.fill == "#ff0000"
    assert document.layers[-1].text == "夏日"


def test_set_text_defaults_to_top_visible_text_layer():
    assert set_text(_text_doc(), None, "新品").layers[-1].text == "新品"


def test_set_text_rejects_image_layers():
    with pytest.raises(EditError):
        set_text(_doc(), "base", "hello")
    with pytest.raises(LayerMissing):
        set_text(_doc(), None, "hello")


def test_flatten_draws_text_layers():
    document = LayerDocument(
        width=80,
        height=80,
        layers=[
            Layer(
                id="text-1",
                kind=LayerKind.TEXT,
                name="Hi",
                width=70,
                height=40,
                transform=Transform(x=5, y=20),
                text="Hi",
                font_size=28,
                fill="#000000",
            )
        ],
    )

    flat = Image.open(BytesIO(flatten(document, {})))
    pixels = [flat.getpixel((x, y))[:3] for y in range(80) for x in range(80)]

    assert any(pixel != (255, 255, 255) for pixel in pixels)

    skipped = Image.open(BytesIO(flatten(document, {}, include_text=False)))
    assert all(
        skipped.getpixel((x, y))[:3] == (255, 255, 255) for y in range(80) for x in range(80)
    )


def test_flatten_empty_text_does_not_draw_layer_name():
    document = LayerDocument(
        width=80,
        height=80,
        layers=[
            Layer(
                id="text-1",
                kind=LayerKind.TEXT,
                name="Hi",
                width=70,
                height=40,
                transform=Transform(x=5, y=20),
                text="",
                font_size=28,
                fill="#000000",
            )
        ],
    )

    flat = Image.open(BytesIO(flatten(document, {})))

    assert all(flat.getpixel((x, y))[:3] == (255, 255, 255) for y in range(80) for x in range(80))


def test_split_document_is_background_subject_and_text():
    document = split_document(
        _doc(80, 60),
        background_id=uuid.uuid4(),
        subject_id=uuid.uuid4(),
        texts=[TextBox("夏日", 10, 8, 40, 16)],
        subject_hash="abc",
    )

    assert [layer.id for layer in document.layers] == [
        BACKGROUND_LAYER_ID,
        SUBJECT_LAYER_ID,
        "text-1",
    ]
    assert already_split(document)
    assert document.layers[-1].text == "夏日"
    assert already_promoted(document, "abc")


def test_mask_hash_is_stable_for_the_same_selection():
    mask = Image.new("L", (32, 32), 0)
    mask.paste(255, (4, 4, 12, 12))

    assert mask_hash(overlay_png(mask)) == mask_hash(overlay_png(mask))


def test_brush_loop_selects_the_enclosed_area():
    loop = [(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75)]

    mask = rasterize_strokes((200, 200), [loop], radius=0.02)

    assert mask.getpixel((100, 100)) == 255
    assert mask.getpixel((4, 4)) == 0


def test_two_point_stroke_only_covers_the_band():
    mask = rasterize_strokes((200, 200), [[(0.2, 0.5), (0.8, 0.5)]], radius=0.02)

    assert mask.getpixel((100, 100)) == 255
    assert mask.getpixel((100, 40)) == 0


def test_circle_mask_covers_the_clicked_point():
    mask = _circles((100, 80), [(0.5, 0.5)])

    assert mask.getpixel((50, 40)) == 255
    assert mask.getpixel((0, 0)) == 0


def test_dashscope_edit_size_stays_within_model_limits():
    assert min(_fit_edit_size(426, 240)) >= 512
    assert max(_fit_edit_size(8000, 4000)) <= 2048


def test_cover_size_grows_the_shorter_edge_to_the_ratio():
    assert cover_size(320, 240, Ratio.LANDSCAPE_16_9) == (426, 240)
    assert cover_size(320, 240, Ratio.SQUARE) == (320, 320)
    assert cover_size(240, 320, Ratio.SQUARE) == (320, 320)


def test_flatten_can_keep_transparent_background():
    asset_id = uuid.uuid4()
    document = _doc(80, 80)
    document.layers[0].asset_id = asset_id
    raw = _png((0, 0, 0, 0), (80, 80), box=(20, 20, 60, 60))

    flat = Image.open(BytesIO(flatten(document, {asset_id: raw}, background=TRANSPARENT)))

    assert flat.getpixel((4, 4))[3] == 0
    assert flat.getpixel((40, 40))[3] == 255
