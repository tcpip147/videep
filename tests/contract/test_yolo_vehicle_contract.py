from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from examples.yolo_vehicle.models import VehicleConfig, VehiclePluginError
from examples.yolo_vehicle.preprocess import Plugin as PreprocessPlugin

from videep.algorithms.contracts import AlgorithmContext, AlgorithmRole
from videep.algorithms.loader import validate_component


def test_example_plugins_implement_contract_1_1_without_importing_ml_dependencies() -> None:
    for role in AlgorithmRole:
        module = importlib.import_module(f"examples.yolo_vehicle.{role.value}")
        component = validate_component(module.Plugin(), role)
        assert component.contract_version == "1.1"


def test_missing_model_and_unknown_config_key_report_config_target(tmp_path: Path) -> None:
    with pytest.raises(VehiclePluginError, match=r"\[config\].*detector_model"):
        VehicleConfig.from_mapping(
            {"detector_model": tmp_path / "missing.pt", "classifier_model": tmp_path / "c.ts"}
        )
    with pytest.raises(VehiclePluginError, match=r"\[config\].*mystery"):
        VehicleConfig.from_mapping(
            {"detector_model": "d.pt", "classifier_model": "c.ts", "mystery": 1},
            require_files=False,
        )


def test_device_mismatch_is_rejected_before_first_frame(tmp_path: Path) -> None:
    detector, classifier = tmp_path / "d.pt", tmp_path / "c.ts"
    detector.touch()
    classifier.touch()
    plugin = PreprocessPlugin()
    context = AlgorithmContext(
        "nvidia",
        "1",
        0,
        object(),
        {"detector_model": str(detector), "classifier_model": str(classifier), "device_id": "0"},
    )
    with pytest.raises(RuntimeError, match="device_id"):
        plugin.initialize(context)
