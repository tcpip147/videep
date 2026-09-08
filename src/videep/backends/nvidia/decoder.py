from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from typing import Protocol

from videep.core.capabilities import PixelFormat, PlaneLayout
from videep.core.frame import GpuFrame, Plane
from videep.core.sync import SyncState, SyncToken

from .interop import NvidiaResource, NvidiaResourcePool


@dataclass(frozen=True, slots=True)
class DecodedSurface:
    handle: object
    sequence: int
    pts: int
    width: int
    height: int
    pitch: int
    size: int
    pixel_format: PixelFormat = PixelFormat.NV12
    event: object = None
    dlpack_exporter: object | None = None


class DecodeDriver(Protocol):
    def decode(self, source: object) -> Iterable[DecodedSurface]: ...

    def close(self) -> None: ...


class NvidiaDecoder:
    def __init__(self, driver: DecodeDriver, pool: NvidiaResourcePool, source: object) -> None:
        self._driver = driver
        self._pool = pool
        self._source = source
        self._closed = False

    async def __aiter__(self) -> AsyncIterator[GpuFrame]:
        if self._closed:
            raise RuntimeError("decoder is closed")
        surfaces = iter(self._driver.decode(self._source))
        sentinel = object()
        next_surface = getattr(self._driver, "next_surface", None)
        while True:
            surface = (
                await asyncio.to_thread(next_surface, surfaces, sentinel)
                if callable(next_surface)
                else await asyncio.to_thread(next, surfaces, sentinel)
            )
            if surface is sentinel:
                break
            assert isinstance(surface, DecodedSurface)
            resource = NvidiaResource(
                surface.handle, self._pool.device_id, surface.size, surface.dlpack_exporter
            )
            lease = self._pool.adopt(resource, owner="decoder")
            yield GpuFrame(
                frame_id=f"frame-{surface.sequence}",
                sequence=surface.sequence,
                pts=surface.pts,
                time_base=(1, 1_000_000),
                pixel_format=surface.pixel_format,
                dimensions=(surface.width, surface.height),
                device_id=self._pool.device_id,
                planes=(Plane(0, surface.pitch, surface.size, PlaneLayout.PITCH_LINEAR),),
                resource_lease=lease,
                sync_token=SyncToken("nvidia", surface.event, surface.sequence, SyncState.SIGNALED),
                writable=True,
            )

    async def close(self) -> None:
        if not self._closed:
            self._driver.close()
            close_source = getattr(self._source, "close", None)
            if callable(close_source):
                await asyncio.to_thread(close_source)
            self._closed = True
