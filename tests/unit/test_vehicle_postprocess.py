from __future__ import annotations

from examples.yolo_vehicle.kernels import clip_box, rgb_luma


def test_overlay_box_is_clipped_to_frame_edges() -> None:
    assert clip_box((-5, -3, 700, 500), 640, 480) == (0, 0, 640, 480)


def test_configured_rgb_colors_produce_distinct_nv12_luma_values() -> None:
    assert rgb_luma((255, 0, 0)) != rgb_luma((0, 255, 0))
    assert all(16 <= rgb_luma(color) <= 235 for color in ((0, 0, 0), (255, 255, 255)))


def test_overlay_uses_visible_white_luma() -> None:
    assert rgb_luma((255, 255, 255)) == 235
