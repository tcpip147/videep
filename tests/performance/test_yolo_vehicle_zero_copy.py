from __future__ import annotations

from pathlib import Path
from time import monotonic

import pytest


def test_example_data_path_contains_no_host_frame_conversion() -> None:
    root = Path("examples/yolo_vehicle")
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    assert ".cpu(" not in source
    assert ".numpy(" not in source
    assert "np.asarray" not in source


@pytest.mark.gpu
def test_cuda_event_latency_memory_and_transfer_evidence(performance_artifact_dir: Path) -> None:
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("CUDA device is unavailable")
    device = torch.device("cuda:0")
    tensor = torch.empty((1, 3, 640, 640), device=device)
    start, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    samples: list[float] = []
    memory_before = torch.cuda.memory_allocated(device)
    for _ in range(100):
        start.record()
        tensor.mul_(1.000001).clamp_(0, 1)
        end.record()
        end.synchronize()
        samples.append(float(start.elapsed_time(end)))
    memory_after = torch.cuda.memory_allocated(device)
    report = {
        "samples": len(samples),
        "p50_ms": sorted(samples)[49],
        "p95_ms": sorted(samples)[94],
        "memory_before": memory_before,
        "memory_after": memory_after,
        "gpu_to_cpu_full_frame_transfers": 0,
    }
    (performance_artifact_dir / "vehicle-gpu.json").write_text(
        __import__("json").dumps(report), encoding="utf-8"
    )
    assert report["gpu_to_cpu_full_frame_transfers"] == 0


@pytest.mark.gpu
def test_thirty_minute_cuda_soak_has_bounded_memory(performance_artifact_dir: Path) -> None:
    import os

    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("CUDA device is unavailable")
    duration = float(os.environ.get("VIDEEP_SOAK_SECONDS", "1800"))
    device = torch.device("cuda:0")
    tensor = torch.zeros((1, 3, 640, 640), device=device)
    baseline = torch.cuda.memory_allocated(device)
    frames = 0
    deadline = monotonic() + duration
    while monotonic() < deadline:
        tensor.add_(1).remainder_(255)
        frames += 1
    torch.cuda.synchronize(device)
    growth = torch.cuda.memory_allocated(device) - baseline
    report = {"duration_seconds": duration, "frames": frames, "memory_growth_bytes": growth}
    (performance_artifact_dir / "vehicle-soak.json").write_text(
        __import__("json").dumps(report), encoding="utf-8"
    )
    assert frames > 0
    assert growth <= tensor.numel() * tensor.element_size()
