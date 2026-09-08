from __future__ import annotations

import pytest
from examples.yolo_vehicle.models import VehicleConfig, VehiclePluginError


def test_vehicle_config_accepts_supported_targets_without_opening_models() -> None:
    config = VehicleConfig.from_mapping(
        {
            "detector_model": "detector.pt",
            "classifier_model": "classifier.ts",
            "target_classes": ["car", "truck"],
        },
        require_files=False,
    )
    assert config.target_classes == ("car", "truck")


@pytest.mark.parametrize(
    "field,value",
    [("detection_confidence", 1.1), ("max_vehicles", 0), ("target_classes", ["person"])],
)
def test_vehicle_config_rejects_invalid_values(field: str, value: object) -> None:
    with pytest.raises(VehiclePluginError):
        VehicleConfig.from_mapping(
            {"detector_model": "d.pt", "classifier_model": "c.ts", field: value},
            require_files=False,
        )
