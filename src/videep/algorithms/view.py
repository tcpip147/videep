"""알고리즘 호출 범위로 제한되는 무복사 GPU 프레임 뷰."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from types import MappingProxyType
from typing import Any, Protocol, cast


class _DLPackExporter(Protocol):
    def __dlpack__(self, **kwargs: object) -> object: ...


class ExpiredFrameViewError(RuntimeError):
    """호출 범위가 끝난 프레임 뷰에 접근했다."""


class FrameView:
    """DLPack exporter만 노출하며 GPU 리소스 소유권은 노출하지 않는다."""

    __slots__ = (
        "_active",
        "_consumer_stream",
        "_device",
        "_exporter",
        "_frame_id",
        "_metadata",
        "_writable",
    )

    def __init__(
        self,
        exporter: object,
        *,
        consumer_stream: object,
        device: tuple[int, int] | None = None,
        frame_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        writable: bool = False,
    ) -> None:
        if consumer_stream is None:
            raise ValueError("DLPack 뷰에는 소비자 GPU 스트림이 필요합니다")
        if not callable(getattr(exporter, "__dlpack__", None)):
            raise TypeError("GPU 리소스가 DLPack 내보내기를 지원하지 않습니다")
        self._exporter = exporter
        self._consumer_stream = consumer_stream
        self._device = device
        self._frame_id = frame_id
        self._metadata = MappingProxyType(dict(metadata or {}))
        self._writable = writable
        self._active = True

    def _ensure_active(self) -> None:
        if not self._active:
            raise ExpiredFrameViewError("알고리즘 호출 범위가 끝난 FrameView입니다")

    @property
    def frame_id(self) -> str | None:
        self._ensure_active()
        return self._frame_id

    @property
    def metadata(self) -> Mapping[str, Any]:
        self._ensure_active()
        return self._metadata

    @property
    def active(self) -> bool:
        return self._active

    @property
    def writable(self) -> bool:
        self._ensure_active()
        return self._writable

    def __dlpack_device__(self) -> tuple[int, int]:
        self._ensure_active()
        if self._device is not None:
            return self._device
        query = getattr(self._exporter, "__dlpack_device__", None)
        if not callable(query):
            raise TypeError("DLPack 장치 질의를 지원하지 않는 GPU 리소스입니다")
        result = query()
        if (
            not isinstance(result, tuple)
            or len(result) != 2
            or not all(isinstance(value, int) for value in result)
        ):
            raise TypeError("유효하지 않은 DLPack 장치 정보입니다")
        return cast(tuple[int, int], result)

    def __dlpack__(
        self,
        *,
        stream: object | None = None,
        max_version: tuple[int, int] | None = None,
        dl_device: tuple[int, int] | None = None,
        copy: bool | None = None,
    ) -> object:
        self._ensure_active()
        if copy is True:
            raise BufferError("FrameView에서는 DLPack 복사가 금지됩니다")
        selected_stream = self._consumer_stream if stream is None else stream
        kwargs: dict[str, object] = {"stream": selected_stream, "copy": False}
        if max_version is not None:
            kwargs["max_version"] = max_version
        if dl_device is not None:
            if dl_device != self.__dlpack_device__():
                raise BufferError("다른 장치로의 DLPack 복사가 금지됩니다")
            kwargs["dl_device"] = dl_device
        exporter = cast(_DLPackExporter, self._exporter).__dlpack__
        try:
            return exporter(**kwargs)
        except TypeError as exc:
            raise TypeError(
                "DLPack exporter가 stream 및 copy=False 계약을 지원하지 않습니다"
            ) from exc

    def expire(self) -> None:
        self._active = False
        self._exporter = None

    def __enter__(self) -> FrameView:
        self._ensure_active()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.expire()


@contextmanager
def scoped_frame_view(
    exporter: object,
    *,
    consumer_stream: object,
    device: tuple[int, int] | None = None,
    frame_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    writable: bool = False,
) -> Iterator[FrameView]:
    """호출 종료 시 반드시 만료되는 ``FrameView``를 만든다."""

    view = FrameView(
        exporter,
        consumer_stream=consumer_stream,
        device=device,
        frame_id=frame_id,
        metadata=metadata,
        writable=writable,
    )
    try:
        yield view
    finally:
        view.expire()
