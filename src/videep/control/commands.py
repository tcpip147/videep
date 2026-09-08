"""제어 플레인 명령 모델."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class CommandKind(StrEnum):
    START = "start"
    STOP = "stop"
    STATUS = "status"


@dataclass(frozen=True, slots=True)
class Command:
    kind: CommandKind
    run_id: str | None = None
    configuration: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if _contains_frame_payload(self.configuration):
            raise ValueError("제어 명령에는 프레임 픽셀이나 GPU 핸들을 포함할 수 없습니다")


def _contains_frame_payload(value: object) -> bool:
    if isinstance(value, Mapping):
        forbidden = {"pixels", "frame", "gpu_handle", "native_handle"}
        return bool(forbidden.intersection(map(str, value))) or any(
            _contains_frame_payload(item) for item in value.values()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_frame_payload(item) for item in value)
    return False
