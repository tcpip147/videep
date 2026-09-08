from __future__ import annotations

from videep.config import AlgorithmSpec, PipelineConfig


def _base(algorithms: dict[str, object]) -> dict[str, object]:
    return {
        "input_uri": "rtsp://source/live",
        "output_uri": "rtsp://sink/live",
        "backend": "nvidia",
        "device_id": "0",
        "algorithms": algorithms,
    }


def test_legacy_string_algorithm_references_remain_supported() -> None:
    config = PipelineConfig.from_mapping(
        _base(
            {role: f"plugins.{role}:plugin" for role in ("preprocess", "inference", "postprocess")}
        )
    )
    assert config.algorithms.reference_for("preprocess") == "plugins.preprocess:plugin"
    assert config.algorithms.options_for("preprocess") == {}


def test_algorithm_object_reference_exposes_per_stage_options() -> None:
    config = PipelineConfig.from_mapping(
        _base(
            {
                role: {
                    "reference": f"examples.yolo_vehicle.{role}:plugin",
                    "options": {"config_path": "vehicle.json"},
                }
                for role in ("preprocess", "inference", "postprocess")
            }
        )
    )
    assert isinstance(config.algorithms.preprocess, AlgorithmSpec)
    assert config.algorithms.options_for("preprocess")["config_path"] == "vehicle.json"
