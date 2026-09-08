from __future__ import annotations

import pytest
from examples.yolo_vehicle.inference import Plugin
from examples.yolo_vehicle.models import (
    VehicleAnalysisResult,
    VehicleClassification,
    VehicleDetection,
)


def test_result_joins_classification_by_detection_id() -> None:
    detection = VehicleDetection(7, 1, 2, 20, 30, "car", 0.9)
    result = VehicleAnalysisResult(
        "frame-1", (detection,), (VehicleClassification(7, "소형", 0.8),)
    )
    result.validate()
    assert "size" not in result.as_metadata()[0]


def test_duplicate_detection_id_is_rejected() -> None:
    item = VehicleDetection(1, 0, 0, 5, 5, "car", 0.8)
    with pytest.raises(ValueError):
        VehicleAnalysisResult("frame-1", (item, item)).validate()


def test_clipped_coordinates_stay_inside_frame() -> None:
    clipped = VehicleDetection(1, -3, -2, 20, 30, "truck", 0.7).clipped(10, 12)
    assert (clipped.x1, clipped.y1, clipped.x2, clipped.y2) == (0, 0, 10, 12)


def test_detector_box_is_smoothed_and_retained_during_brief_miss() -> None:
    plugin = Plugin()
    plugin._tracks = {}
    plugin._next_track_id = 0
    first = plugin._stabilize([VehicleDetection(0, 0, 0, 20, 20, "car", 0.9)])[0]
    second = plugin._stabilize([VehicleDetection(0, 2, 2, 22, 22, "car", 0.8)])[0]

    assert second.detection_id == first.detection_id
    assert 0 < second.x1 < 2
    assert plugin._stabilize([])[0].detection_id == first.detection_id
