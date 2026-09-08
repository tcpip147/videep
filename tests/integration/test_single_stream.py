from __future__ import annotations

from dataclasses import dataclass

import pytest

from videep.backends.nvidia.backend import NvidiaBackend
from videep.backends.nvidia.decoder import DecodedSurface


class DecodeDriver:
    closed = False

    def decode(self, source: object):  # type: ignore[no-untyped-def]
        del source
        for sequence in range(5):
            yield DecodedSurface(object(), sequence, sequence * 1_000, 16, 16, 16, 384)

    def close(self) -> None:
        self.closed = True


class EncodeDriver:
    def __init__(self) -> None:
        self.sequences: list[int] = []
        self.closed = False

    def encode_gpu(self, resource: object, frame: object) -> None:
        del resource
        self.sequences.append(frame.sequence)  # type: ignore[attr-defined]

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


@dataclass
class FakeSdk:
    decoder: DecodeDriver
    encoder: EncodeDriver

    def create_decode_driver(self, device_id: str) -> DecodeDriver:
        return self.decoder

    def create_encode_driver(self, output_uri: str, device_id: str) -> EncodeDriver:
        return self.encoder


@pytest.mark.asyncio
async def test_five_frames_remain_ordered_and_resources_are_released() -> None:
    decode_driver, encode_driver = DecodeDriver(), EncodeDriver()
    backend = NvidiaBackend(sdk=FakeSdk(decode_driver, encode_driver))  # type: ignore[arg-type]
    pool = backend.create_pool("0", 5)
    decoder = backend.create_decoder("input.mp4", pool)
    encoder = backend.create_encoder("output.mp4", "0")

    async for frame in decoder:
        frame.resource_lease.transfer("decoder", "encoder")
        await encoder.encode(frame)
    await encoder.flush()
    await decoder.close()
    await encoder.close()

    assert encode_driver.sequences == [0, 1, 2, 3, 4]
    assert pool.available == 5
    assert decode_driver.closed and encode_driver.closed
