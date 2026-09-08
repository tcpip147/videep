from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from videep.core.frame import GpuFrame


@dataclass(frozen=True, slots=True)
class EncodedPacket:
    data: bytes
    timestamp: int | None = None


class PacketSink(Protocol):
    def write(self, access_unit: bytes, *, timestamp: int | None = None) -> None: ...

    def close(self) -> None: ...


class EncodeDriver(Protocol):
    def encode_gpu(
        self, resource: object, frame: GpuFrame
    ) -> EncodedPacket | bytes | Iterable[EncodedPacket | bytes] | None: ...

    def flush(self) -> None: ...

    def close(self) -> None: ...


class NvidiaEncoder:
    def __init__(
        self, driver: EncodeDriver, *, owner: str = "encoder", sink: PacketSink | None = None
    ) -> None:
        self._driver = driver
        self._owner = owner
        self._sink = sink
        self._closed = False
        self.encoded_packets = 0
        self.encoded_bytes = 0

    async def encode(self, frame: GpuFrame) -> None:
        if self._closed:
            raise RuntimeError("encoder is closed")
        lease = frame.resource_lease
        with lease.borrow_view(self._owner) as borrowed:
            encoded = self._driver.encode_gpu(borrowed.resource, frame)
        if self._sink is not None and encoded is not None:
            packets = (
                encoded
                if isinstance(encoded, Iterable) and not isinstance(encoded, bytes)
                else (encoded,)
            )
            for packet in packets:
                if isinstance(packet, bytes):
                    self._sink.write(packet)
                    self.encoded_packets += 1
                    self.encoded_bytes += len(packet)
                else:
                    self._sink.write(packet.data, timestamp=packet.timestamp)
                    self.encoded_packets += 1
                    self.encoded_bytes += len(packet.data)
        lease.release(self._owner)

    def telemetry(self) -> dict[str, int]:
        values = {
            "encoded_packets": self.encoded_packets,
            "encoded_bytes": self.encoded_bytes,
        }
        if self._sink is not None:
            values["rtp_packets"] = int(getattr(self._sink, "sent_packets", 0))
            values["rtp_payload_bytes"] = int(getattr(self._sink, "sent_bytes", 0))
            values["h264_nal_units"] = int(getattr(self._sink, "nal_units", 0))
            values["h264_sps_units"] = int(getattr(self._sink, "sps_units", 0))
            values["h264_pps_units"] = int(getattr(self._sink, "pps_units", 0))
            values["h264_idr_units"] = int(getattr(self._sink, "idr_units", 0))
            values["rtp_timestamp"] = int(getattr(self._sink, "last_rtp_timestamp", 0))
            values["rtp_timestamp_fallbacks"] = int(getattr(self._sink, "timestamp_fallbacks", 0))
        return values

    async def flush(self) -> None:
        self._driver.flush()

    async def close(self) -> None:
        if not self._closed:
            self._driver.close()
            if self._sink is not None:
                self._sink.close()
            self._closed = True
