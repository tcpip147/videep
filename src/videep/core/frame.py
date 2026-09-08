from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from .capabilities import PixelFormat, PlaneLayout
from .lease import GpuResourceLease
from .sync import SyncToken


@dataclass(frozen=True, slots=True)
class Plane:
    offset: int
    pitch: int
    size: int
    layout: PlaneLayout = PlaneLayout.PITCH_LINEAR
    modifier: str | None = None

    def __post_init__(self) -> None:
        if self.offset < 0 or self.pitch <= 0 or self.size <= 0:
            raise ValueError("plane의 offset, pitch 또는 size가 유효하지 않습니다")


@dataclass(frozen=True, slots=True)
class GpuFrame:
    frame_id: str
    sequence: int
    pts: int
    time_base: tuple[int, int]
    pixel_format: PixelFormat
    dimensions: tuple[int, int]
    device_id: str
    planes: tuple[Plane, ...]
    resource_lease: GpuResourceLease
    sync_token: SyncToken
    metadata: Mapping[str, object] = field(default_factory=dict)
    writable: bool = False

    def __post_init__(self) -> None:
        if not self.frame_id or self.sequence < 0 or self.pts < 0:
            raise ValueError("프레임 식별자, 순서 또는 PTS가 유효하지 않습니다")
        if self.time_base[0] <= 0 or self.time_base[1] <= 0:
            raise ValueError("time_base는 양수여야 합니다")
        if any(value <= 0 for value in self.dimensions) or not self.planes:
            raise ValueError("프레임 크기와 plane은 유효해야 합니다")
        if self.device_id != self.resource_lease.device_id:
            raise ValueError("프레임과 lease의 장치가 일치하지 않습니다")
        if self.sync_token.backend_id != self.resource_lease.backend_id:
            raise ValueError("동기화 토큰과 lease의 백엔드가 일치하지 않습니다")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def format(self) -> PixelFormat:
        """계약 문서의 ``format`` 명칭과 호환되는 읽기 전용 별칭."""
        return self.pixel_format
