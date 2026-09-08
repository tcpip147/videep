from __future__ import annotations

import pytest

from videep.algorithms.artifacts import (
    ArtifactClosedError,
    ArtifactError,
    FrameArtifacts,
    GpuArtifact,
)


def test_gpu_artifact_is_released_once_when_store_closes() -> None:
    released: list[object] = []
    value = object()
    store = FrameArtifacts("frame-1", "nvidia", "0")
    store.put_gpu(
        "detector.input", GpuArtifact(value, "nvidia", "0", "preprocess", releaser=released.append)
    )

    assert store.get_gpu("detector.input", "inference").value is value
    store.close()
    store.close()

    assert released == [value]


def test_names_are_unique_across_metadata_and_gpu_artifacts() -> None:
    store = FrameArtifacts("frame-1", "nvidia", "0")
    store.put_metadata("result", (1, 2))
    with pytest.raises(ArtifactError):
        store.put_gpu("result", GpuArtifact(object(), "nvidia", "0", "inference"))


def test_cross_device_artifact_and_large_host_payload_are_rejected() -> None:
    store = FrameArtifacts("frame-1", "nvidia", "0")
    with pytest.raises(ArtifactError):
        store.put_gpu("wrong", GpuArtifact(object(), "nvidia", "1", "preprocess"))
    with pytest.raises(ArtifactError):
        store.put_metadata("pixels", bytearray(1024))


def test_closed_store_rejects_access() -> None:
    store = FrameArtifacts("frame-1", "nvidia", "0")
    store.close()
    with pytest.raises(ArtifactClosedError):
        store.put_metadata("late", 1)
