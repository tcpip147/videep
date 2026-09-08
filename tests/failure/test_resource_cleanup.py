from __future__ import annotations

import pytest

from videep.backends.nvidia.interop import NvidiaInteropError, NvidiaResource, NvidiaResourcePool


@pytest.mark.asyncio
async def test_released_lease_returns_resource_to_pool() -> None:
    pool = NvidiaResourcePool(
        device_id="0", capacity=1, allocator=lambda size: NvidiaResource(object(), "0", size)
    )
    lease = await pool.acquire("decoder")
    lease.release("decoder")

    assert pool.available == 1


@pytest.mark.asyncio
async def test_allocation_failure_does_not_create_a_live_resource() -> None:
    def fail(size: int) -> NvidiaResource:
        raise MemoryError("GPU allocation failed")

    pool = NvidiaResourcePool(device_id="0", capacity=1, allocator=fail)
    with pytest.raises(MemoryError, match="GPU allocation failed"):
        await pool.acquire("decoder")

    assert pool.available == 0


@pytest.mark.asyncio
async def test_exhausted_pool_fails_instead_of_allocating_host_memory() -> None:
    pool = NvidiaResourcePool(device_id="0", capacity=1, allocator=None)

    with pytest.raises(NvidiaInteropError, match="exhausted"):
        await pool.acquire("decoder")
