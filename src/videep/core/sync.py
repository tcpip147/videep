from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable


class SyncState(StrEnum):
    PENDING = "pending"
    SIGNALED = "signaled"


@dataclass(frozen=True, slots=True)
class SyncToken:
    backend_id: str
    handle: object
    value: int = 0
    state: SyncState = SyncState.PENDING

    def __post_init__(self) -> None:
        if not self.backend_id or self.value < 0:
            raise ValueError("유효하지 않은 동기화 토큰입니다")


@runtime_checkable
class Synchronizer(Protocol):
    async def wait(self, token: SyncToken, *, consumer_stream: object | None = None) -> None: ...
    async def signal(
        self, token: SyncToken, *, producer_stream: object | None = None
    ) -> SyncToken: ...
