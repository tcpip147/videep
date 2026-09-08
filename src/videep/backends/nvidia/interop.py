from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from itertools import count
from threading import Lock
from typing import Any, cast

from videep.core.lease import GpuResourceLease
from videep.core.sync import SyncState, SyncToken


class NvidiaInteropError(RuntimeError):
    """Raised when a native resource cannot be exposed without copying."""


@dataclass(frozen=True, slots=True)
class NvidiaResource:
    """Opaque NVIDIA allocation; the handle is deliberately backend-private."""

    handle: object
    device_id: str
    size: int
    dlpack_exporter: object | None = None

    def _exporter(self) -> object:
        return self.dlpack_exporter if self.dlpack_exporter is not None else self.handle

    def __dlpack__(
        self,
        *,
        stream: object | None = None,
        max_version: tuple[int, int] | None = None,
        dl_device: tuple[int, int] | None = None,
        copy: bool | None = None,
    ) -> object:
        if copy is True:
            raise BufferError("NVIDIA GPU 리소스의 호스트 복사는 금지됩니다")
        exporter = self._exporter()
        method = getattr(exporter, "__dlpack__", None)
        if callable(method):
            kwargs: dict[str, object] = {"stream": stream, "copy": False}
            if max_version is not None:
                kwargs["max_version"] = max_version
            if dl_device is not None:
                kwargs["dl_device"] = dl_device
            try:
                return method(**kwargs)
            except TypeError:
                return method(stream=stream)
        legacy = getattr(exporter, "dlpack", None)
        if callable(legacy):
            return legacy(stream)
        raise NvidiaInteropError("NVIDIA 리소스가 DLPack 내보내기를 지원하지 않습니다")

    def __dlpack_device__(self) -> tuple[int, int]:
        exporter = self._exporter()
        method = getattr(exporter, "__dlpack_device__", None)
        if callable(method):
            result = method()
            return int(result[0]), int(result[1])
        legacy = getattr(exporter, "dlpack_device", None)
        if callable(legacy):
            result = legacy()
            return int(result[0]), int(result[1])
        return (2, int(self.device_id))


class NvidiaResourcePool:
    def __init__(
        self,
        *,
        device_id: str,
        capacity: int = 4,
        allocator: Callable[[int], NvidiaResource] | None = None,
    ) -> None:
        if capacity < 1:
            raise ValueError("pool capacity must be at least one")
        self.device_id = device_id
        self.capacity = capacity
        self._allocator = allocator
        self._available: list[NvidiaResource] = []
        self._allocated = 0
        self._ids = count()
        self._lock = Lock()

    async def acquire(self, owner: str, size: int = 1) -> GpuResourceLease:
        with self._lock:
            if self._available:
                resource = self._available.pop()
            elif self._allocator is not None and self._allocated < self.capacity:
                resource = self._allocator(size)
                if resource.device_id != self.device_id:
                    raise NvidiaInteropError("allocator returned a resource from another device")
                self._allocated += 1
            else:
                raise NvidiaInteropError("NVIDIA GPU resource pool is exhausted")
            resource_id = f"nvidia:{self.device_id}:{next(self._ids)}"
        return GpuResourceLease(
            resource_id=resource_id,
            backend_id="nvidia",
            device_id=self.device_id,
            resource=resource,
            owner=owner,
            releaser=self._release,
        )

    def adopt(self, resource: NvidiaResource, *, owner: str) -> GpuResourceLease:
        if resource.device_id != self.device_id:
            raise NvidiaInteropError("cannot adopt a resource from another device")
        return GpuResourceLease(
            resource_id=f"nvidia:{self.device_id}:{next(self._ids)}",
            backend_id="nvidia",
            device_id=self.device_id,
            resource=resource,
            owner=owner,
            releaser=self._release,
        )

    def _release(self, resource: object) -> None:
        if not isinstance(resource, NvidiaResource):
            raise NvidiaInteropError("foreign resource returned to NVIDIA pool")
        with self._lock:
            if len(self._available) < self.capacity:
                self._available.append(resource)

    @property
    def available(self) -> int:
        with self._lock:
            return len(self._available)

    async def close(self) -> None:
        with self._lock:
            self._available.clear()
            self._allocated = 0


class NvidiaSynchronizer:
    """Dispatches waits/signals to native event objects without a CPU wait."""

    def __init__(self, stream: object = 0) -> None:
        self.stream = stream

    async def wait(self, token: SyncToken, *, consumer_stream: object | None = None) -> None:
        handle = token.handle
        if handle is None and token.state is SyncState.SIGNALED:
            return
        wait = getattr(handle, "wait", None) or getattr(handle, "wait_stream", None)
        if wait is None:
            raise NvidiaInteropError("synchronization handle has no device-side wait")
        wait(consumer_stream)

    async def signal(self, token: SyncToken, *, producer_stream: object | None = None) -> SyncToken:
        handle = token.handle
        signal = getattr(handle, "record", None) or getattr(handle, "signal", None)
        if signal is None:
            raise NvidiaInteropError("synchronization handle has no device-side signal")
        signal(producer_stream)
        return token


class _DLPackView:
    def __init__(self, exporter: object, stream: object | None) -> None:
        self._exporter = exporter
        self._stream = stream

    def __dlpack__(self, *, stream: object | None = None) -> object:
        selected_stream = self._stream if stream is None else stream
        exporter = cast(Any, self._exporter).__dlpack__
        return exporter(stream=selected_stream)

    def __dlpack_device__(self) -> object:
        method = getattr(self._exporter, "__dlpack_device__", None)
        if method is None:
            # kDLCUDA, device zero. NVIDIA resources never masquerade as CPU memory.
            return (2, 0)
        return method()


@contextmanager
def dlpack_view(
    lease: GpuResourceLease, *, owner: str, stream: object | None = None
) -> Iterator[object]:
    """Borrow a zero-copy DLPack producer while keeping the lease alive."""

    with lease.borrow_view(owner) as borrowed:
        resource = borrowed.resource
        exporter = getattr(resource, "dlpack_exporter", None) or resource
        method = getattr(exporter, "__dlpack__", None)
        if method is None:
            raise NvidiaInteropError("resource does not support DLPack zero-copy export")
        yield _DLPackView(exporter, stream)
