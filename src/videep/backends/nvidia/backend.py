from __future__ import annotations

import os
import sys
from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import cast

from videep.backends.base import ResourcePool
from videep.core.capabilities import DeviceCapability, PixelFormat, PlaneLayout
from videep.transport.rtsp import RtspAnnounceSink, RtspPullSource

from .decoder import DecodeDriver, NvidiaDecoder
from .encoder import EncodeDriver, NvidiaEncoder
from .interop import NvidiaResource, NvidiaResourcePool, NvidiaSynchronizer
from .sdk_drivers import PyNvDecodeDriver, PyNvEncodeDriver


class NvidiaBackendUnavailable(RuntimeError):
    pass


_DLL_DIRECTORY_HANDLES: list[object] = []


def _add_cuda_dll_directories() -> None:
    """Windows wheel이 요구할 수 있는 설치된 CUDA 런타임 경로를 등록한다."""
    if _DLL_DIRECTORY_HANDLES or sys.platform != "win32" or not hasattr(os, "add_dll_directory"):
        return
    candidates = {
        Path(value) / "bin"
        for name, value in os.environ.items()
        if name == "CUDA_PATH" or name.startswith("CUDA_PATH_V")
    }
    for directory in sorted(candidates):
        if directory.is_dir():
            _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(directory)))


def _load_sdk() -> ModuleType:
    _add_cuda_dll_directories()
    try:
        return import_module("PyNvVideoCodec")
    except (ImportError, OSError, RuntimeError) as error:
        raise NvidiaBackendUnavailable(
            "PyNvVideoCodec를 불러올 수 없습니다. NVIDIA 의존성과 CUDA 런타임을 확인하세요"
        ) from error


class NvidiaBackend:
    backend_id = "nvidia"

    def __init__(self, *, device_id: str = "0", sdk: ModuleType | None = None) -> None:
        self.device_id = device_id
        self.sdk = sdk if sdk is not None else _load_sdk()

    @classmethod
    def available(cls) -> bool:
        try:
            _load_sdk()
        except NvidiaBackendUnavailable:
            return False
        return True

    def enumerate_devices(self) -> tuple[DeviceCapability, ...]:
        return (self.capabilities(),)

    def capabilities(self) -> DeviceCapability:
        return DeviceCapability(
            backend_id=self.backend_id,
            device_id=self.device_id,
            codecs=frozenset(("h264", "hevc")),
            pixel_formats=frozenset((PixelFormat.NV12, PixelFormat.P010)),
            plane_layouts=frozenset((PlaneLayout.PITCH_LINEAR,)),
            external_handle_types=frozenset(("cuda-device-pointer",)),
            synchronization_types=frozenset(("cuda-event",)),
            zero_copy_interop=frozenset(("dlpack",)),
        )

    def create_pool(
        self,
        device_id: str,
        capacity: int = 4,
        allocator: Callable[[int], NvidiaResource] | None = None,
    ) -> NvidiaResourcePool:
        if device_id != self.device_id:
            raise ValueError(f"backend is bound to device {self.device_id}, not {device_id}")
        if allocator is None:
            allocator = getattr(self.sdk, "allocate_gpu_resource", None)
        return NvidiaResourcePool(device_id=self.device_id, capacity=capacity, allocator=allocator)

    def create_decoder(self, input_uri: str, pool: ResourcePool) -> NvidiaDecoder:
        if not isinstance(pool, NvidiaResourcePool):
            raise TypeError("NVIDIA decoder에는 NvidiaResourcePool이 필요합니다")
        factory = getattr(self.sdk, "create_decode_driver", None)
        driver = (
            cast(DecodeDriver, factory(self.device_id))
            if factory is not None
            else PyNvDecodeDriver(self.sdk, self.device_id)
        )
        source: object = (
            RtspPullSource(input_uri) if input_uri.lower().startswith("rtsp://") else input_uri
        )
        return NvidiaDecoder(driver, pool, source)

    def create_encoder(self, output_uri: str, device_id: str) -> NvidiaEncoder:
        if device_id != self.device_id:
            raise ValueError(f"backend is bound to device {self.device_id}, not {device_id}")
        factory = getattr(self.sdk, "create_encode_driver", None)
        sink = RtspAnnounceSink(output_uri) if output_uri.lower().startswith("rtsp://") else None
        driver = (
            cast(EncodeDriver, factory(output_uri, device_id))
            if factory is not None
            else PyNvEncodeDriver(self.sdk, output_uri, device_id)
        )
        return NvidiaEncoder(driver, sink=sink)

    def create_synchronizer(self, device_id: str) -> NvidiaSynchronizer:
        if device_id != self.device_id:
            raise ValueError(f"backend is bound to device {self.device_id}, not {device_id}")
        return NvidiaSynchronizer()
