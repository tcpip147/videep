from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock


class LeaseError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BorrowedGpuResource:
    resource: object
    resource_id: str
    generation: int


class GpuResourceLease:
    def __init__(
        self,
        *,
        resource_id: str,
        backend_id: str,
        device_id: str,
        resource: object,
        owner: str,
        generation: int = 0,
        releaser: Callable[[object], None] | None = None,
    ) -> None:
        if not all((resource_id, backend_id, device_id, owner)):
            raise ValueError("lease 식별자와 소유자는 비어 있을 수 없습니다")
        self.resource_id = resource_id
        self.backend_id = backend_id
        self.device_id = device_id
        self.generation = generation
        self._resource = resource
        self._owner = owner
        self._releaser = releaser
        self._active = True
        self._borrows = 0
        self._lock = RLock()

    @property
    def owner(self) -> str:
        return self._owner

    @property
    def active(self) -> bool:
        return self._active

    def transfer(self, current_owner: str, new_owner: str) -> None:
        with self._lock:
            self._assert_owner(current_owner)
            if self._borrows:
                raise LeaseError("빌린 뷰가 활성 상태인 동안 소유권을 이전할 수 없습니다")
            if not new_owner:
                raise ValueError("새 소유자는 비어 있을 수 없습니다")
            self._owner = new_owner

    @contextmanager
    def borrow_view(self, owner: str) -> Iterator[BorrowedGpuResource]:
        with self._lock:
            self._assert_owner(owner)
            self._borrows += 1
            view = BorrowedGpuResource(self._resource, self.resource_id, self.generation)
        try:
            yield view
        finally:
            with self._lock:
                self._borrows -= 1

    def release(self, owner: str) -> None:
        with self._lock:
            self._assert_owner(owner)
            if self._borrows:
                raise LeaseError("빌린 뷰가 활성 상태인 동안 lease를 해제할 수 없습니다")
            self._active = False
            if self._releaser is not None:
                self._releaser(self._resource)

    def _assert_owner(self, owner: str) -> None:
        if not self._active:
            raise LeaseError("이미 해제된 lease입니다")
        if owner != self._owner:
            raise LeaseError(f"lease 소유자가 아닙니다: {owner}")
