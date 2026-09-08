from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from functools import reduce


class PixelFormat(StrEnum):
    NV12 = "nv12"
    P010 = "p010"
    RGBA8 = "rgba8"


class PlaneLayout(StrEnum):
    PITCH_LINEAR = "pitch-linear"
    BLOCK_LINEAR = "block-linear"


@dataclass(frozen=True, slots=True)
class DeviceCapability:
    backend_id: str
    device_id: str
    codecs: frozenset[str]
    pixel_formats: frozenset[PixelFormat]
    plane_layouts: frozenset[PlaneLayout]
    external_handle_types: frozenset[str]
    synchronization_types: frozenset[str]
    zero_copy_interop: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.backend_id or not self.device_id:
            raise ValueError("backend_id와 device_id는 비어 있을 수 없습니다")


@dataclass(frozen=True, slots=True)
class CapabilitySet:
    devices: frozenset[str]
    codecs: frozenset[str]
    pixel_formats: frozenset[PixelFormat]
    plane_layouts: frozenset[PlaneLayout]
    external_handle_types: frozenset[str]
    synchronization_types: frozenset[str]
    zero_copy_interop: frozenset[str]

    @classmethod
    def from_device(cls, capability: DeviceCapability) -> CapabilitySet:
        return cls(
            frozenset((capability.device_id,)),
            capability.codecs,
            capability.pixel_formats,
            capability.plane_layouts,
            capability.external_handle_types,
            capability.synchronization_types,
            capability.zero_copy_interop,
        )

    def intersection(self, other: CapabilitySet) -> CapabilitySet:
        return CapabilitySet(
            *(getattr(self, name) & getattr(other, name) for name in self.__dataclass_fields__)
        )

    def supports_zero_copy(self) -> bool:
        return bool(
            self.devices
            and self.pixel_formats
            and self.plane_layouts
            and self.synchronization_types
            and self.zero_copy_interop
        )


def negotiate(capabilities: Iterable[CapabilitySet]) -> CapabilitySet:
    candidates = tuple(capabilities)
    if not candidates:
        raise ValueError("협상할 capability가 없습니다")
    result = reduce(CapabilitySet.intersection, candidates)
    if not result.supports_zero_copy():
        raise ValueError("호환되는 무복사 GPU 경로가 없습니다")
    return result
