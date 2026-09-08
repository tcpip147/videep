from __future__ import annotations

import pytest

from videep.algorithms.view import ExpiredFrameViewError, scoped_frame_view


class RecordingExporter:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] | None = None

    def __dlpack_device__(self) -> tuple[int, int]:
        return (2, 0)

    def __dlpack__(self, **kwargs: object) -> str:
        self.kwargs = kwargs
        return "capsule"


def test_dlpack_forces_no_copy_and_passes_consumer_stream() -> None:
    exporter = RecordingExporter()
    with scoped_frame_view(exporter, consumer_stream=17) as view:
        assert view.__dlpack__() == "capsule"
    assert exporter.kwargs == {"stream": 17, "copy": False}


def test_explicit_copy_is_rejected() -> None:
    with (
        scoped_frame_view(RecordingExporter(), consumer_stream=17) as view,
        pytest.raises(BufferError, match="복사"),
    ):
        view.__dlpack__(copy=True)


def test_cross_device_request_is_rejected() -> None:
    with (
        scoped_frame_view(RecordingExporter(), consumer_stream=17) as view,
        pytest.raises(BufferError, match="다른 장치"),
    ):
        view.__dlpack__(dl_device=(2, 1))


def test_view_expires_after_call_scope() -> None:
    with scoped_frame_view(RecordingExporter(), consumer_stream=17) as view:
        assert view.active
    assert not view.active
    with pytest.raises(ExpiredFrameViewError):
        view.__dlpack__()


def test_runtime_ownership_is_not_exposed() -> None:
    with scoped_frame_view(RecordingExporter(), consumer_stream=17) as view:
        assert not hasattr(view, "resource_lease")
        assert not hasattr(view, "release")
