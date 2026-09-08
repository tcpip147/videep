from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum

from .frame import GpuFrame


class SignalKind(StrEnum):
    EOS = "eos"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class StreamSignal:
    kind: SignalKind
    error: BaseException | None = None

    def __post_init__(self) -> None:
        if self.kind is SignalKind.ERROR and self.error is None:
            raise ValueError("ERROR 신호에는 오류가 필요합니다")
        if self.kind is SignalKind.EOS and self.error is not None:
            raise ValueError("EOS 신호에는 오류를 포함할 수 없습니다")


EOS = StreamSignal(SignalKind.EOS)


class FrameQueue[T: GpuFrame]:
    def __init__(self, maxsize: int = 4) -> None:
        if maxsize < 1:
            raise ValueError("큐 용량은 1 이상이어야 합니다")
        self._queue: asyncio.Queue[T | StreamSignal] = asyncio.Queue(maxsize)
        self.high_watermark = 0
        self.put_wait_count = 0

    @property
    def maxsize(self) -> int:
        return self._queue.maxsize

    def qsize(self) -> int:
        return self._queue.qsize()

    async def put(self, item: T | StreamSignal) -> None:
        if self._queue.full():
            self.put_wait_count += 1
        await self._queue.put(item)
        self.high_watermark = max(self.high_watermark, self._queue.qsize())

    async def get(self) -> T | StreamSignal:
        item = await self._queue.get()
        self._queue.task_done()
        return item

    def put_nowait(self, item: T | StreamSignal) -> None:
        self._queue.put_nowait(item)
        self.high_watermark = max(self.high_watermark, self._queue.qsize())

    async def join(self) -> None:
        await self._queue.join()
