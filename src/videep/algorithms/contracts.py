"""사용자 제공 알고리즘의 백엔드 중립 공개 계약."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

CONTRACT_VERSION = "1.1"


class AlgorithmRole(StrEnum):
    PREPROCESS = "preprocess"
    INFERENCE = "inference"
    POSTPROCESS = "postprocess"


@dataclass(frozen=True, slots=True)
class AlgorithmContext:
    """런타임이 구성요소에 제공하는 비소유 실행 정보."""

    backend_id: str
    device_id: str
    stream: object
    capabilities: object
    options: Mapping[str, Any] = field(default_factory=dict)
    metrics: object | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", MappingProxyType(dict(self.options)))


@runtime_checkable
class AlgorithmComponent(Protocol):
    """전처리, 추론 또는 후처리 구성요소가 구현해야 하는 수명 주기."""

    role: AlgorithmRole | str
    contract_version: str

    def validate(self, capabilities: object) -> None: ...

    def initialize(self, context: AlgorithmContext) -> None: ...

    def process(self, frame_view: Any, *args: object) -> object: ...

    def close(self) -> None: ...


def contract_major(version: str) -> int:
    """계약 버전의 주 버전을 반환한다."""

    try:
        major, _minor = version.split(".", maxsplit=1)
        return int(major)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"유효하지 않은 알고리즘 계약 버전: {version!r}") from exc


def contract_minor(version: str) -> int:
    try:
        _major, minor = version.split(".", maxsplit=1)
        return int(minor)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"유효하지 않은 알고리즘 계약 버전: {version!r}") from exc
