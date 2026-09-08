"""지연 로딩 PyTorch 기반 GPU 전처리 및 표시 연산."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, cast


def _torch() -> Any:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("vehicle-example 선택 의존성 torch가 필요합니다") from exc
    return torch


def nv12_to_detector_input(frame: object, size: int = 640) -> tuple[object, tuple[float, int, int]]:
    torch = _torch()
    tensor = torch.from_dlpack(frame)
    if not tensor.is_cuda:
        raise TypeError("preprocess: DLPack 프레임은 CUDA 장치에 있어야 합니다")
    raw = tensor.squeeze(-1)
    storage_height, width = raw.shape
    height = storage_height * 2 // 3
    y = raw[:height].float()
    uv = raw[height:].reshape(height // 2, width // 2, 2).float()
    uv = torch.nn.functional.interpolate(
        uv.permute(2, 0, 1).unsqueeze(0), size=(height, width), mode="nearest"
    ).squeeze(0)
    yy, uu, vv = y, uv[0] - 128.0, uv[1] - 128.0
    rgb = torch.stack((yy + 1.402 * vv, yy - 0.344136 * uu - 0.714136 * vv, yy + 1.772 * uu))
    rgb = rgb.clamp_(0, 255).div_(255.0)
    scale = min(size / width, size / height)
    resized_width, resized_height = round(width * scale), round(height * scale)
    resized = torch.nn.functional.interpolate(
        rgb.unsqueeze(0), size=(resized_height, resized_width), mode="bilinear", align_corners=False
    )
    pad_x, pad_y = (size - resized_width) // 2, (size - resized_height) // 2
    output = torch.nn.functional.pad(
        resized,
        (pad_x, size - resized_width - pad_x, pad_y, size - resized_height - pad_y),
        value=114 / 255,
    )
    return output.contiguous(), (scale, pad_x, pad_y)


def draw_overlay(
    frame: object,
    analysis: Iterable[Mapping[str, object]],
    *,
    writable: bool,
    colors: Mapping[str, tuple[int, int, int]] | None = None,
) -> None:
    if not writable:
        raise RuntimeError("overlay: writable GPU 프레임이 필요합니다")
    torch = _torch()
    tensor = torch.from_dlpack(frame).squeeze(-1)
    height = tensor.shape[0] * 2 // 3
    y_plane = tensor[:height]
    uv_plane = tensor[height:].reshape(height // 2, tensor.shape[1] // 2, 2)
    for item in analysis:
        box = cast(tuple[float, float, float, float], item["box"])
        x1, y1, x2, y2 = (int(value) for value in box)
        x1, y1, x2, y2 = clip_box((x1, y1, x2, y2), y_plane.shape[1], height)
        if x2 <= x1 or y2 <= y1:
            continue
        # BT.601 limited-range green: Y=145, U=54, V=34.
        luma = 145
        thickness = 2
        y_plane[y1 : min(y1 + thickness, y2), x1:x2] = luma
        y_plane[max(y1, y2 - thickness) : y2, x1:x2] = luma
        y_plane[y1:y2, x1 : min(x1 + thickness, x2)] = luma
        y_plane[y1:y2, max(x1, x2 - thickness) : x2] = luma
        ux1, ux2 = x1 // 2, (x2 + 1) // 2
        uy1, uy2 = y1 // 2, (y2 + 1) // 2
        uv_plane[uy1 : min(uy1 + 1, uy2), ux1:ux2, 0] = 54
        uv_plane[uy1 : min(uy1 + 1, uy2), ux1:ux2, 1] = 34
        uv_plane[max(uy1, uy2 - 1) : uy2, ux1:ux2, 0] = 54
        uv_plane[max(uy1, uy2 - 1) : uy2, ux1:ux2, 1] = 34
        uv_plane[uy1:uy2, ux1 : min(ux1 + 1, ux2), 0] = 54
        uv_plane[uy1:uy2, ux1 : min(ux1 + 1, ux2), 1] = 34
        uv_plane[uy1:uy2, max(ux1, ux2 - 1) : ux2, 0] = 54
        uv_plane[uy1:uy2, max(ux1, ux2 - 1) : ux2, 1] = 34
    # NVENC owns an internal stream that cannot consume a Python CUDA event.
    # Complete these small in-place writes before handing the surface to it.
    torch.cuda.current_stream(tensor.device).synchronize()
    del torch


def clip_box(box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    return max(0, x1), max(0, y1), min(width, x2), min(height, y2)


def rgb_luma(rgb: tuple[int, int, int]) -> int:
    red, green, blue = rgb
    return max(16, min(235, round(16 + (65.738 * red + 129.057 * green + 25.064 * blue) / 256)))
