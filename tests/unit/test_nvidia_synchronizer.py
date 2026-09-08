from __future__ import annotations

import pytest

from videep.backends.nvidia.interop import NvidiaInteropError, NvidiaSynchronizer
from videep.core.sync import SyncState, SyncToken


@pytest.mark.asyncio
async def test_signaled_token_without_handle_needs_no_wait() -> None:
    synchronizer = NvidiaSynchronizer()
    token = SyncToken("nvidia", None, state=SyncState.SIGNALED)
    await synchronizer.wait(token, consumer_stream=0)


@pytest.mark.asyncio
async def test_pending_token_without_handle_is_rejected() -> None:
    synchronizer = NvidiaSynchronizer()
    token = SyncToken("nvidia", None, state=SyncState.PENDING)
    with pytest.raises(NvidiaInteropError, match="device-side wait"):
        await synchronizer.wait(token, consumer_stream=0)
