from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from enum import StrEnum
from typing import Any

from videep.core.capabilities import PixelFormat


class ErrorPolicy(StrEnum):
    STOP = "stop"


class ShutdownPolicy(StrEnum):
    DRAIN = "drain"
    IMMEDIATE = "immediate"


@dataclass(frozen=True, slots=True)
class AlgorithmSpec:
    reference: str
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.reference.count(":") != 1 or not all(self.reference.split(":")):
            raise ValueError("알고리즘 reference는 module:object 형식이어야 합니다")
        object.__setattr__(self, "options", dict(self.options))


@dataclass(frozen=True, slots=True)
class AlgorithmReferences:
    preprocess: str | AlgorithmSpec
    inference: str | AlgorithmSpec
    postprocess: str | AlgorithmSpec

    def __post_init__(self) -> None:
        for item in fields(self):
            role, value = item.name, getattr(self, item.name)
            reference = value.reference if isinstance(value, AlgorithmSpec) else value
            if reference.count(":") != 1 or not all(reference.split(":")):
                raise ValueError(f"{role} 참조는 module:object 형식이어야 합니다")

    def reference_for(self, role: str) -> str:
        value = getattr(self, role)
        return value.reference if isinstance(value, AlgorithmSpec) else value

    def options_for(self, role: str) -> Mapping[str, Any]:
        value = getattr(self, role)
        return value.options if isinstance(value, AlgorithmSpec) else {}


@dataclass(frozen=True, slots=True)
class MeasurementConfig:
    enabled: bool = True
    sample_interval_seconds: float = 1.0

    def __post_init__(self) -> None:
        if self.sample_interval_seconds <= 0:
            raise ValueError("측정 간격은 양수여야 합니다")


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    input_uri: str
    output_uri: str
    backend: str
    device_id: str
    algorithms: AlgorithmReferences
    queue_capacity: int | Mapping[str, int] = 4
    pixel_format: PixelFormat = PixelFormat.NV12
    dimensions: tuple[int, int] | None = None
    error_policy: ErrorPolicy = ErrorPolicy.STOP
    shutdown_policy: ShutdownPolicy = ShutdownPolicy.DRAIN
    measurement: MeasurementConfig = field(default_factory=MeasurementConfig)

    def __post_init__(self) -> None:
        if not all((self.input_uri, self.output_uri, self.backend, self.device_id)):
            raise ValueError("입력, 출력, 백엔드 및 장치는 필수입니다")
        capacities = (
            self.queue_capacity.values()
            if isinstance(self.queue_capacity, Mapping)
            else (self.queue_capacity,)
        )
        if any(value < 1 for value in capacities):
            raise ValueError("모든 큐 용량은 1 이상이어야 합니다")
        if self.dimensions is not None and any(value <= 0 for value in self.dimensions):
            raise ValueError("프레임 크기는 양수여야 합니다")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> PipelineConfig:
        allowed = {field.name for field in cls.__dataclass_fields__.values()}
        unknown = set(raw) - allowed
        if unknown:
            raise ValueError(f"알 수 없는 구성 항목: {', '.join(sorted(unknown))}")
        values = dict(raw)
        algorithms = values.get("algorithms")
        if isinstance(algorithms, Mapping):
            parsed = {
                key: AlgorithmSpec(**value) if isinstance(value, Mapping) else value
                for key, value in algorithms.items()
            }
            values["algorithms"] = AlgorithmReferences(**parsed)
        measurement = values.get("measurement")
        if isinstance(measurement, Mapping):
            values["measurement"] = MeasurementConfig(**measurement)
        if isinstance(values.get("pixel_format"), str):
            values["pixel_format"] = PixelFormat(values["pixel_format"])
        if isinstance(values.get("dimensions"), list):
            values["dimensions"] = tuple(values["dimensions"])
        return cls(**values)
