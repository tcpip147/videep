from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from examples.yolo_vehicle.models import (
    VehicleAnalysisResult,
    VehicleClassification,
    VehicleConfig,
    VehicleDetection,
)

from videep.algorithms.artifacts import FrameArtifacts
from videep.config import PipelineConfig


def test_vehicle_present_absent_and_occluded_results_keep_frame_order() -> None:
    stores = [FrameArtifacts(f"frame-{index}", "nvidia", "0") for index in range(3)]
    results = (
        VehicleAnalysisResult("frame-0", (VehicleDetection(0, 1, 1, 20, 20, "car", 0.9),)),
        VehicleAnalysisResult("frame-1", ()),
        VehicleAnalysisResult(
            "frame-2",
            (VehicleDetection(0, 5, 5, 12, 10, "truck", 0.6),),
            (VehicleClassification(0, "미분류", 0.4),),
        ),
    )
    for store, result in zip(stores, results, strict=True):
        result.validate()
        store.put_metadata("vehicle.analysis", result.as_metadata())

    assert [store.frame_id for store in stores] == ["frame-0", "frame-1", "frame-2"]
    assert stores[1].get_metadata("vehicle.analysis") == ()
    assert "size" not in stores[2].get_metadata("vehicle.analysis")[0]  # type: ignore[index]
    for store in stores:
        store.close()
    assert all(store.closed for store in stores)


def test_model_and_display_settings_are_replaceable_only_through_json(tmp_path: Path) -> None:
    detector, classifier = tmp_path / "new-yolo.pt", tmp_path / "new-size.ts"
    detector.touch()
    classifier.touch()
    config = VehicleConfig.from_mapping(
        {
            "detector_model": str(detector),
            "classifier_model": str(classifier),
            "detection_confidence": 0.8,
            "box_colors": {
                "소형": [1, 2, 3],
                "중형": [4, 5, 6],
                "대형": [7, 8, 9],
                "미분류": [10, 11, 12],
            },
        }
    )
    assert config.detector_model == detector
    assert config.detection_confidence == 0.8
    assert config.box_colors["대형"] == (7, 8, 9)


def test_example_pipeline_configuration_loads_without_core_changes() -> None:
    import json

    raw = json.loads(
        Path("examples/yolo_vehicle/pipeline.example.json").read_text(encoding="utf-8")
    )
    config = PipelineConfig.from_mapping(raw)
    assert config.algorithms.reference_for("inference") == "examples.yolo_vehicle.inference:Plugin"


@pytest.mark.gpu
@pytest.mark.asyncio
async def test_real_gpu_rtsp_pipeline_detects_classifies_and_releases_resources() -> None:
    config_path = os.environ.get("VIDEEP_VEHICLE_PIPELINE_CONFIG")
    if not config_path:
        pytest.skip("VIDEEP_VEHICLE_PIPELINE_CONFIG is required")
    import json

    from videep.algorithms.contracts import AlgorithmRole
    from videep.algorithms.loader import load_algorithm
    from videep.backends.nvidia.backend import NvidiaBackend
    from videep.core.pipeline import PipelineRuntime

    config = PipelineConfig.from_mapping(json.loads(Path(config_path).read_text(encoding="utf-8")))
    runtime = PipelineRuntime(
        config,
        NvidiaBackend(),
        {
            role: load_algorithm(config.algorithms.reference_for(role.value), role)
            for role in AlgorithmRole
        },
    )
    task = asyncio.create_task(runtime.run())
    deadline = asyncio.get_running_loop().time() + 60
    while runtime.telemetry().get("frames_out", 0) < 30 and not task.done():
        if asyncio.get_running_loop().time() >= deadline:
            runtime.request_stop()
            pytest.fail("60초 안에 출력 프레임 30개를 처리하지 못했습니다")
        await asyncio.sleep(0.1)
    runtime.request_stop()
    result = await asyncio.wait_for(task, timeout=30)
    assert result.error is None
    assert result.frames_out >= 30
    assert runtime.telemetry().get("vehicles_detected", 0) >= 0
