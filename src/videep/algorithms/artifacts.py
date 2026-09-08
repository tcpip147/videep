"""프레임 처리 단계 사이에서 산출물을 안전하게 전달하는 계약."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


class ArtifactError(RuntimeError):
    pass


class ArtifactClosedError(ArtifactError):
    pass


@dataclass(slots=True)
class GpuArtifact:
    value: object
    backend_id: str
    device_id: str
    producer_stage: str
    ready_token: object | None = None
    releaser: Callable[[object], None] | None = None
    _released: bool = False

    @property
    def released(self) -> bool:
        return self._released

    def release(self) -> None:
        if self._released:
            raise ArtifactClosedError("GPU 산출물이 이미 해제되었습니다")
        self._released = True
        if self.releaser is not None:
            self.releaser(self.value)


def _is_small_metadata(value: object) -> bool:
    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    if isinstance(value, tuple):
        return len(value) <= 256 and all(_is_small_metadata(item) for item in value)
    if isinstance(value, Mapping):
        return len(value) <= 256 and all(
            isinstance(key, str) and _is_small_metadata(item) for key, item in value.items()
        )
    return False


class FrameArtifacts:
    def __init__(self, frame_id: str, backend_id: str, device_id: str) -> None:
        if not all((frame_id, backend_id, device_id)):
            raise ValueError("프레임, 백엔드 및 장치 식별자는 비어 있을 수 없습니다")
        self.frame_id = frame_id
        self.backend_id = backend_id
        self.device_id = device_id
        self._metadata: dict[str, object] = {}
        self._gpu: dict[str, GpuArtifact] = {}
        self._order: list[str] = []
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def metadata(self) -> Mapping[str, object]:
        self._ensure_open()
        return MappingProxyType(self._metadata)

    def put_metadata(self, name: str, value: object) -> None:
        self._validate_new_name(name)
        if not _is_small_metadata(value):
            raise ArtifactError("메타데이터에는 작은 불변 값만 등록할 수 있습니다")
        self._metadata[name] = value
        self._order.append(name)

    def get_metadata(self, name: str, expected_type: type[Any] | None = None) -> object:
        self._ensure_open()
        if name not in self._metadata:
            raise ArtifactError(f"메타데이터 산출물이 없습니다: {name}")
        value = self._metadata[name]
        if expected_type is not None and not isinstance(value, expected_type):
            raise ArtifactError(f"메타데이터 형식이 다릅니다: {name}")
        return value

    def put_gpu(self, name: str, artifact: GpuArtifact) -> None:
        self._validate_new_name(name)
        if artifact.backend_id != self.backend_id or artifact.device_id != self.device_id:
            raise ArtifactError("GPU 산출물의 백엔드 또는 장치가 프레임과 다릅니다")
        from videep.core.lease import GpuResourceLease

        if isinstance(artifact.value, GpuResourceLease):
            raise ArtifactError("기반 GPU 프레임 lease를 산출물로 등록할 수 없습니다")
        self._gpu[name] = artifact
        self._order.append(name)

    def get_gpu(self, name: str, consumer_stage: str) -> GpuArtifact:
        self._ensure_open()
        if not consumer_stage:
            raise ValueError("소비 단계는 비어 있을 수 없습니다")
        if name not in self._gpu:
            raise ArtifactError(f"GPU 산출물이 없습니다: {name}")
        artifact = self._gpu[name]
        if artifact.released:
            raise ArtifactClosedError(f"GPU 산출물이 이미 해제되었습니다: {name}")
        return artifact

    def remove(self, name: str) -> None:
        self._ensure_open()
        if name in self._gpu:
            self._gpu.pop(name).release()
        elif name in self._metadata:
            self._metadata.pop(name)
        else:
            raise ArtifactError(f"산출물이 없습니다: {name}")
        self._order.remove(name)

    def close(self) -> None:
        if self._closed:
            return
        for name in reversed(self._order):
            artifact = self._gpu.get(name)
            if artifact is not None and not artifact.released:
                artifact.release()
        self._gpu.clear()
        self._metadata.clear()
        self._order.clear()
        self._closed = True

    def _validate_new_name(self, name: str) -> None:
        self._ensure_open()
        if not name:
            raise ValueError("산출물 이름은 비어 있을 수 없습니다")
        if name in self._metadata or name in self._gpu:
            raise ArtifactError(f"산출물 이름이 중복되었습니다: {name}")

    def _ensure_open(self) -> None:
        if self._closed:
            raise ArtifactClosedError("프레임 산출물 저장소가 이미 닫혔습니다")

    def __enter__(self) -> FrameArtifacts:
        self._ensure_open()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()
