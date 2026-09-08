from __future__ import annotations

import pytest

from videep.backends.nvidia.interop import NvidiaResource, NvidiaResourcePool, dlpack_view


class DLPackProducer:
    def __init__(self) -> None:
        self.requests = 0

    def __dlpack__(self, *, stream: object | None = None) -> object:
        self.requests += 1
        return object()


@pytest.mark.asyncio
async def test_dlpack_interop_borrows_original_gpu_resource_without_host_copy() -> None:
    producer = DLPackProducer()
    resource = NvidiaResource(object(), "0", 1024, producer)
    pool = NvidiaResourcePool(device_id="0", capacity=1)
    lease = pool.adopt(resource, owner="algorithm")

    with dlpack_view(lease, owner="algorithm", stream=object()) as view:
        assert view.__dlpack__() is not None  # type: ignore[attr-defined]
        assert producer.requests == 1

    lease.release("algorithm")
    assert pool.available == 1
