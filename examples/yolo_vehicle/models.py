"""차량 예제 설정과 작은 추론 결과 모델."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Self

SIZE_CLASSES = ("소형", "중형", "대형", "미분류")
SUPPORTED_TARGETS = frozenset(("car", "bus", "truck"))


class VehiclePluginError(RuntimeError):
    def __init__(self, stage: str, target: str, message: str) -> None:
        super().__init__(f"[{stage}] {target}: {message}")
        self.stage = stage
        self.target = target


@dataclass(frozen=True, slots=True)
class VehicleConfig:
    detector_model: Path
    classifier_model: Path | None = None
    device_id: str = "0"
    detection_confidence: float = 0.35
    classification_confidence: float = 0.60
    iou_threshold: float = 0.45
    max_vehicles: int = 32
    target_classes: tuple[str, ...] = ("car", "bus", "truck")
    min_crop_size: int = 16
    box_colors: dict[str, tuple[int, int, int]] = field(
        default_factory=lambda: {
            "소형": (0, 255, 0),
            "중형": (255, 200, 0),
            "대형": (255, 0, 0),
            "미분류": (160, 160, 160),
        }
    )

    @classmethod
    def from_mapping(cls, raw: dict[str, Any], *, require_files: bool = True) -> Self:
        allowed = set(cls.__dataclass_fields__)
        unknown = set(raw) - allowed
        if unknown:
            raise VehiclePluginError("config", ", ".join(sorted(unknown)), "알 수 없는 키")
        values = dict(raw)
        for key in ("detector_model",):
            if key not in values:
                raise VehiclePluginError("config", key, "필수 모델 경로가 없습니다")
            values[key] = Path(values[key])
            if require_files and not values[key].is_file():
                raise VehiclePluginError(
                    "config", key, f"모델 파일을 읽을 수 없습니다: {values[key]}"
                )
        if "target_classes" in values:
            values["target_classes"] = tuple(values["target_classes"])
        if "box_colors" in values:
            values["box_colors"] = {
                key: tuple(color) for key, color in values["box_colors"].items()
            }
        config = cls(**values)
        config.validate()
        return config

    @classmethod
    def from_json(cls, path: Path, *, require_files: bool = True) -> Self:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VehiclePluginError(
                "config", str(path), f"JSON을 읽을 수 없습니다: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise VehiclePluginError("config", str(path), "최상위 값은 객체여야 합니다")
        return cls.from_mapping(raw, require_files=require_files)

    def validate(self) -> None:
        for name, value in (
            ("detection_confidence", self.detection_confidence),
            ("classification_confidence", self.classification_confidence),
            ("iou_threshold", self.iou_threshold),
        ):
            if not 0 <= value <= 1:
                raise VehiclePluginError("config", name, "0 이상 1 이하여야 합니다")
        if self.max_vehicles < 1 or self.min_crop_size < 1:
            raise VehiclePluginError("config", "limits", "최댓값과 최소 ROI는 1 이상이어야 합니다")
        if not self.target_classes or not set(self.target_classes) <= SUPPORTED_TARGETS:
            raise VehiclePluginError("config", "target_classes", "car, bus, truck만 지원합니다")
        if set(self.box_colors) != set(SIZE_CLASSES):
            raise VehiclePluginError("config", "box_colors", "모든 차급 색상이 필요합니다")
        if any(
            len(color) != 3 or any(not 0 <= channel <= 255 for channel in color)
            for color in self.box_colors.values()
        ):
            raise VehiclePluginError("config", "box_colors", "RGB 채널은 0~255여야 합니다")


@dataclass(frozen=True, slots=True)
class VehicleDetection:
    detection_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    object_class: str
    confidence: float

    def clipped(self, width: int, height: int) -> VehicleDetection:
        return VehicleDetection(
            self.detection_id,
            max(0.0, min(float(width - 1), self.x1)),
            max(0.0, min(float(height - 1), self.y1)),
            max(0.0, min(float(width), self.x2)),
            max(0.0, min(float(height), self.y2)),
            self.object_class,
            self.confidence,
        )

    def validate(self) -> None:
        if self.detection_id < 0 or self.x1 >= self.x2 or self.y1 >= self.y2:
            raise ValueError("유효하지 않은 차량 검출 좌표입니다")
        if self.object_class not in SUPPORTED_TARGETS or not 0 <= self.confidence <= 1:
            raise ValueError("유효하지 않은 차량 종류 또는 신뢰도입니다")


@dataclass(frozen=True, slots=True)
class VehicleClassification:
    detection_id: int
    size_class: str
    confidence: float

    def validate(self) -> None:
        if (
            self.detection_id < 0
            or self.size_class not in SIZE_CLASSES
            or not 0 <= self.confidence <= 1
        ):
            raise ValueError("유효하지 않은 차급 결과입니다")


@dataclass(frozen=True, slots=True)
class VehicleAnalysisResult:
    frame_id: str
    detections: tuple[VehicleDetection, ...]
    classifications: tuple[VehicleClassification, ...] = ()

    def validate(self) -> None:
        ids = {item.detection_id for item in self.detections}
        if len(ids) != len(self.detections):
            raise ValueError("검출 ID가 중복되었습니다")
        classification_ids = {item.detection_id for item in self.classifications}
        if len(classification_ids) != len(self.classifications) or not classification_ids <= ids:
            raise ValueError("차급 결과가 검출 결과와 연결되지 않습니다")

    def as_metadata(self) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "id": item.detection_id,
                "box": (item.x1, item.y1, item.x2, item.y2),
                "class": item.object_class,
                "confidence": item.confidence,
            }
            for item in self.detections
        )


def config_from_options(options: Mapping[str, Any]) -> VehicleConfig:
    values = dict(options)
    config_path = values.get("config_path")
    if config_path:
        return VehicleConfig.from_json(Path(config_path))
    return VehicleConfig.from_mapping(values)
