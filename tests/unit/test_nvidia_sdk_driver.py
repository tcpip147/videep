from __future__ import annotations

import ctypes
from types import SimpleNamespace

from videep.backends.nvidia.interop import NvidiaResource
from videep.backends.nvidia.sdk_drivers import PyNvDecodeDriver, PyNvEncodeDriver
from videep.core.capabilities import PixelFormat, PlaneLayout
from videep.core.frame import GpuFrame, Plane
from videep.core.lease import GpuResourceLease
from videep.core.sync import SyncState, SyncToken


class PacketData:
    def __init__(self) -> None:
        self._bsl_data = 0
        self.bsl = 0
        self.pts = 0
        self.decode_flag = 0

    @property
    def bsl_data(self) -> int:
        return self._bsl_data

    @bsl_data.setter
    def bsl_data(self, value: int) -> None:
        if not isinstance(value, int):
            raise TypeError("bsl_data에는 주소 정수가 필요합니다")
        self._bsl_data = value


class Decoder:
    def __init__(self) -> None:
        self.received = b""

    def Decode(self, packet: PacketData) -> list[object]:
        self.received = ctypes.string_at(packet.bsl_data, packet.bsl)
        return []

    def Flush(self) -> list[object]:
        return []


class Sdk:
    PacketData = PacketData
    cudaVideoCodec = SimpleNamespace(H264=4)
    DisplayDecodeLatencyType = SimpleNamespace(LOW=1)
    VideoPacketFlag = SimpleNamespace(ENDOFPICTURE=8)

    def __init__(self) -> None:
        self.decoder = Decoder()
        self.decoder_options: dict[str, object] = {}

    def CreateDecoder(self, **kwargs: object) -> Decoder:
        self.decoder_options = kwargs
        return self.decoder


def test_compressed_packet_uses_native_pointer_with_live_buffer() -> None:
    sdk = Sdk()
    driver = PyNvDecodeDriver(sdk, "0")  # type: ignore[arg-type]
    assert list(driver.decode(iter((b"\x00\x00\x01\x65payload",)))) == []
    assert sdk.decoder.received == b"\x00\x00\x01\x65payload"
    assert "cudacontext" in sdk.decoder_options


class DLPackExporter:
    def __init__(self) -> None:
        self.stream: object | None = None

    def __dlpack__(self, *, stream: object | None = None, **kwargs: object) -> str:
        self.stream = stream
        assert kwargs.get("copy") is False
        return "capsule"

    def __dlpack_device__(self) -> tuple[int, int]:
        return (2, 0)


def test_nvidia_resource_delegates_dlpack_without_exposing_native_handle() -> None:
    exporter = DLPackExporter()
    resource = NvidiaResource(object(), "0", 128, exporter)
    assert resource.__dlpack__(stream=7) == "capsule"
    assert exporter.stream == 7
    assert resource.__dlpack_device__() == (2, 0)


class DecodedNv12Frame:
    shape = [720, 640, 1]
    strides = [640, 1, 1]

    def framesize(self) -> int:
        return 720 * 640

    def getPTS(self) -> int:
        return 3_000


def test_nv12_storage_shape_is_converted_to_visible_dimensions() -> None:
    driver = PyNvDecodeDriver(Sdk(), "0")  # type: ignore[arg-type]
    surface = driver._surface(DecodedNv12Frame())
    assert surface.width == 640
    assert surface.height == 480
    assert surface.size == 720 * 640


def test_nvenc_packet_dicts_are_normalized_to_encoded_packets() -> None:
    packets = PyNvEncodeDriver._packets(
        [
            {"data": b"first", "timestamp": 90_000, "picture_type": 1},
            {"data": b"second", "timestamp": 93_000, "picture_type": 2},
        ],
        0,
    )
    assert [(packet.data, packet.timestamp) for packet in packets] == [
        (b"first", 90_000),
        (b"second", 93_000),
    ]


class RecordingEncoder:
    def __init__(self) -> None:
        self.flags: list[int | None] = []

    def Encode(self, frame: object, flags: int | None = None) -> list[dict[str, object]]:
        del frame
        self.flags.append(flags)
        return [{"data": b"\x00\x00\x00\x01\x65frame", "timestamp": 0}]


class EncodeSdk:
    NV_ENC_PIC_FLAGS = SimpleNamespace(FORCEIDR=2, OUTPUT_SPSPPS=4)

    def __init__(self) -> None:
        self.encoder = RecordingEncoder()

    def CreateEncoder(self, *args: object, **kwargs: object) -> RecordingEncoder:
        del args, kwargs
        return self.encoder


def _gpu_frame(sequence: int) -> GpuFrame:
    resource = NvidiaResource(object(), "0", 128)
    lease = GpuResourceLease(
        resource_id=f"resource-{sequence}",
        backend_id="nvidia",
        device_id="0",
        resource=resource,
        owner="encoder",
    )
    return GpuFrame(
        f"frame-{sequence}",
        sequence,
        sequence * 3_000,
        (1, 90_000),
        PixelFormat.NV12,
        (16, 16),
        "0",
        (Plane(0, 16, 128, PlaneLayout.PITCH_LINEAR),),
        lease,
        SyncToken("nvidia", None, sequence, SyncState.SIGNALED),
    )


def test_nvenc_forces_idr_and_parameter_sets_every_thirty_frames() -> None:
    sdk = EncodeSdk()
    driver = PyNvEncodeDriver(sdk, "unused", "0")  # type: ignore[arg-type]
    resource = NvidiaResource(object(), "0", 128)
    for sequence in range(31):
        driver.encode_gpu(resource, _gpu_frame(sequence))
    assert sdk.encoder.flags[0] == 6
    assert sdk.encoder.flags[1] is None
    assert sdk.encoder.flags[30] == 6
