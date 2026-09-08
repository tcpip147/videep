"""공식 PyNvVideoCodec API를 내부 driver 계약에 맞추는 어댑터."""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Iterable, Iterator
from types import ModuleType
from typing import Any

from videep.core.capabilities import PixelFormat
from videep.core.frame import GpuFrame

from .decoder import DecodedSurface
from .encoder import EncodedPacket
from .interop import NvidiaResource


def _current_cuda_context() -> int:
    """Return the CUDA context active on this thread, if one exists."""

    if sys.platform != "win32":
        return 0
    driver = ctypes.WinDLL("nvcuda.dll")
    context = ctypes.c_void_p()
    result = driver.cuCtxGetCurrent(ctypes.byref(context))
    if result == 3:  # CUDA_ERROR_NOT_INITIALIZED: no caller-owned context yet.
        return 0
    if result != 0:
        raise RuntimeError(f"cuCtxGetCurrent failed with CUDA driver error {result}")
    return int(context.value or 0)


def _next_in_cuda_context(iterator: Iterator[Any], sentinel: object, context: int) -> object:
    if not context or sys.platform != "win32":
        return next(iterator, sentinel)
    driver = ctypes.WinDLL("nvcuda.dll")
    result = driver.cuCtxPushCurrent_v2(ctypes.c_void_p(context))
    if result != 0:
        raise RuntimeError(f"cuCtxPushCurrent failed with CUDA driver error {result}")
    try:
        return next(iterator, sentinel)
    finally:
        popped = ctypes.c_void_p()
        result = driver.cuCtxPopCurrent_v2(ctypes.byref(popped))
        if result != 0:
            raise RuntimeError(f"cuCtxPopCurrent failed with CUDA driver error {result}")


class PyNvDecodeDriver:
    def __init__(self, sdk: ModuleType, device_id: str) -> None:
        self._sdk = sdk
        codec_enum = getattr(sdk, "cudaVideoCodec", sdk).H264
        cuda_context = _current_cuda_context()
        self._cuda_context = cuda_context
        self._decoder = sdk.CreateDecoder(
            gpuid=int(device_id),
            codec=codec_enum,
            cudacontext=cuda_context,
            usedevicememory=True,
            latency=sdk.DisplayDecodeLatencyType.LOW,
        )
        self._sequence = 0

    def next_surface(self, surfaces: Iterator[Any], sentinel: object) -> object:
        """Advance decoding on a worker while making the captured context current."""

        return _next_in_cuda_context(surfaces, sentinel, self._cuda_context)

    def _packet(self, data: bytes, pts: int) -> tuple[object, object]:
        packet = self._sdk.PacketData()
        buffer = ctypes.create_string_buffer(data)
        if hasattr(packet, "bsl_data"):
            packet.bsl_data = ctypes.addressof(buffer)
        if hasattr(packet, "bitstream"):
            packet.bitstream = ctypes.addressof(buffer)
        if hasattr(packet, "bsl"):
            packet.bsl = len(data)
        if hasattr(packet, "size"):
            packet.size = len(data)
        if hasattr(packet, "pts"):
            packet.pts = pts
        flag = getattr(getattr(self._sdk, "VideoPacketFlag", object()), "ENDOFPICTURE", None)
        if flag is not None and hasattr(packet, "decode_flag"):
            packet.decode_flag = flag
        return packet, buffer

    def _surface(self, frame: Any) -> DecodedSurface:
        shape = tuple(int(value) for value in frame.shape)
        strides = tuple(int(value) for value in frame.strides)
        if len(shape) < 2 or len(strides) < 1:
            raise ValueError(f"유효하지 않은 NVDEC 프레임 shape/strides: {shape}/{strides}")
        storage_height, width = shape[0], shape[1]
        # PyNvVideoCodec은 NV12/P010을 Y plane과 UV plane이 세로로 이어진
        # [height * 3 / 2, width, 1] 배열로 노출한다.
        if storage_height % 3:
            raise ValueError(f"NV12/P010 저장 높이는 3의 배수여야 합니다: {storage_height}")
        height = storage_height * 2 // 3
        size = (
            int(frame.framesize())
            if callable(getattr(frame, "framesize", None))
            else storage_height * strides[0]
        )
        pts = int(frame.getPTS()) if callable(getattr(frame, "getPTS", None)) else self._sequence
        surface = DecodedSurface(
            handle=frame,
            sequence=self._sequence,
            pts=pts,
            width=width,
            height=height,
            pitch=strides[0],
            size=size,
            pixel_format=PixelFormat.NV12,
            event=getattr(frame, "event", None),
            dlpack_exporter=frame,
        )
        self._sequence += 1
        return surface

    def decode(self, source: object) -> Iterable[DecodedSurface]:
        if isinstance(source, str):
            raise TypeError("파일 입력은 기존 demuxer 어댑터가 필요합니다")
        iterator = iter(source)  # type: ignore[call-overload]

        def generate() -> Iterator[DecodedSurface]:
            pts = 0
            for access_unit in iterator:
                packet, buffer_owner = self._packet(bytes(access_unit), pts)
                for frame in self._decoder.Decode(packet):
                    yield self._surface(frame)
                del buffer_owner
                pts += 3_000
            for frame in self._decoder.Flush():
                yield self._surface(frame)

        return generate()

    def close(self) -> None:
        self._decoder = None


class PyNvEncodeDriver:
    def __init__(self, sdk: ModuleType, output_uri: str, device_id: str) -> None:
        self._sdk = sdk
        self._output_uri = output_uri
        self._device_id = int(device_id)
        self._encoder: Any = None
        self._frame_count = 0

    def _ensure_encoder(self, frame: GpuFrame) -> Any:
        if self._encoder is None:
            width, height = frame.dimensions
            self._encoder = self._sdk.CreateEncoder(
                width,
                height,
                frame.pixel_format.value.upper(),
                False,
                gpu_id=self._device_id,
                codec="h264",
                tuning_info="low_latency",
                preset="P1",
                fps=30,
                gop=30,
                idrperiod=30,
                bf=0,
                repeatspspps=1,
            )
        return self._encoder

    @staticmethod
    def _packets(result: object, fallback_timestamp: int) -> tuple[EncodedPacket, ...]:
        if result is None:
            return ()
        if isinstance(result, (bytes, bytearray, memoryview)):
            data = bytes(result)
            return (EncodedPacket(data, fallback_timestamp),) if data else ()
        if not isinstance(result, Iterable):
            raise TypeError(f"지원하지 않는 NVENC 반환 형식: {type(result).__name__}")
        packets: list[EncodedPacket] = []
        for item in result:
            if isinstance(item, dict):
                data = item.get("data", b"")
                timestamp = item.get("timestamp", fallback_timestamp)
            else:
                data = item
                timestamp = fallback_timestamp
            if not isinstance(data, (bytes, bytearray, memoryview)):
                raise TypeError(f"NVENC packet data가 bytes가 아닙니다: {type(data).__name__}")
            if data:
                packets.append(EncodedPacket(bytes(data), int(timestamp)))
        return tuple(packets)

    def encode_gpu(self, resource: object, frame: GpuFrame) -> tuple[EncodedPacket, ...] | None:
        native = resource.handle if isinstance(resource, NvidiaResource) else resource
        encoder = self._ensure_encoder(frame)
        if self._frame_count % 30 == 0:
            flags = self._sdk.NV_ENC_PIC_FLAGS
            pic_flags = int(flags.FORCEIDR) | int(flags.OUTPUT_SPSPPS)
            result = encoder.Encode(native, pic_flags)
        else:
            result = encoder.Encode(native)
        self._frame_count += 1
        packets = self._packets(result, frame.pts)
        return packets or None

    def flush(self) -> None:
        if self._encoder is not None:
            self._encoder.EndEncode()

    def close(self) -> None:
        self.flush()
        self._encoder = None
