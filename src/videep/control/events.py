"""프레임 데이터와 분리된 제어 플레인 이벤트."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class EventKind(StrEnum):
    STATE = "state"
    ERROR = "error"
    METRIC = "metric"


@dataclass(frozen=True, slots=True)
class ControlEvent:
    kind: EventKind
    run_id: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        forbidden = {"pixels", "frame", "gpu_handle", "native_handle"}
        if forbidden.intersection(map(str, self.payload)):
            raise ValueError("제어 이벤트에는 프레임 픽셀이나 GPU 핸들을 포함할 수 없습니다")
