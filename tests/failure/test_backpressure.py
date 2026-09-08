from __future__ import annotations

import asyncio

import pytest

from videep.core.capabilities import PixelFormat
from videep.core.frame import GpuFrame, Plane
from videep.core.lease import GpuResourceLease
from videep.core.queue import EOS, FrameQueue, SignalKind, StreamSignal
from videep.core.sync import SyncToken


def make_frame(sequence: int) -> GpuFrame:
    lease = GpuResourceLease(
        resource_id=f"r{sequence}",
        backend_id="fake",
        device_id="gpu0",
        resource=object(),
        owner="producer",
    )
    return GpuFrame(
        f"f{sequence}",
        sequence,
        sequence,
        (1, 30),
        PixelFormat.NV12,
        (1, 1),
        "gpu0",
        (Plane(0, 1, 1),),
        lease,
        SyncToken("fake", object()),
    )


@pytest.mark.asyncio
async def test_bounded_queue_blocks_producer_and_preserves_fifo() -> None:
    queue: FrameQueue[GpuFrame] = FrameQueue(maxsize=1)
    first, second = make_frame(0), make_frame(1)
    await queue.put(first)
    pending = asyncio.create_task(queue.put(second))
    await asyncio.sleep(0)
    assert not pending.done()
    assert await queue.get() is first
    await pending
    assert await queue.get() is second
    assert queue.high_watermark == 1
    assert queue.put_wait_count == 1


@pytest.mark.asyncio
async def test_eos_and_error_are_explicit_fifo_items() -> None:
    queue: FrameQueue[GpuFrame] = FrameQueue(maxsize=3)
    failure = RuntimeError("decode failed")
    await queue.put(make_frame(0))
    await queue.put(EOS)
    assert isinstance(await queue.get(), GpuFrame)
    assert await queue.get() == EOS
    await queue.put(StreamSignal(SignalKind.ERROR, failure))
    signal = await queue.get()
    assert isinstance(signal, StreamSignal)
    assert signal.error is failure


def test_invalid_capacity_and_error_signal_are_rejected() -> None:
    with pytest.raises(ValueError, match="1 이상"):
        FrameQueue(maxsize=0)
    with pytest.raises(ValueError, match="오류"):
        StreamSignal(SignalKind.ERROR)
