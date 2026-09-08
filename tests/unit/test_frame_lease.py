from __future__ import annotations

import pytest

from videep.core.capabilities import PixelFormat
from videep.core.frame import GpuFrame, Plane
from videep.core.lease import GpuResourceLease, LeaseError
from videep.core.sync import SyncToken


def lease(owner: str = "decoder") -> GpuResourceLease:
    return GpuResourceLease(
        resource_id="r1", backend_id="fake", device_id="gpu0", resource=object(), owner=owner
    )


def frame(resource_lease: GpuResourceLease | None = None) -> GpuFrame:
    return GpuFrame(
        frame_id="f0",
        sequence=0,
        pts=0,
        time_base=(1, 30),
        pixel_format=PixelFormat.NV12,
        dimensions=(1920, 1080),
        device_id="gpu0",
        planes=(Plane(0, 1920, 2073600),),
        resource_lease=resource_lease or lease(),
        sync_token=SyncToken("fake", object()),
    )


def test_lease_transfer_invalidates_previous_owner() -> None:
    resource = lease()
    resource.transfer("decoder", "preprocess")
    with pytest.raises(LeaseError, match="소유자"), resource.borrow_view("decoder"):
        pass
    with resource.borrow_view("preprocess") as borrowed:
        assert borrowed.resource_id == "r1"


def test_active_borrow_blocks_transfer_and_release() -> None:
    resource = lease()
    with resource.borrow_view("decoder"):
        with pytest.raises(LeaseError, match="빌린 뷰"):
            resource.transfer("decoder", "next")
        with pytest.raises(LeaseError, match="빌린 뷰"):
            resource.release("decoder")


def test_duplicate_release_and_use_after_release_are_rejected() -> None:
    resource = lease()
    resource.release("decoder")
    with pytest.raises(LeaseError, match="해제"):
        resource.release("decoder")


def test_frame_rejects_device_and_sync_backend_mismatch() -> None:
    resource = lease()
    with pytest.raises(ValueError, match="장치"):
        GpuFrame(
            "f",
            0,
            0,
            (1, 1),
            PixelFormat.NV12,
            (1, 1),
            "gpu1",
            (Plane(0, 1, 1),),
            resource,
            SyncToken("fake", object()),
        )
    with pytest.raises(ValueError, match="백엔드"):
        GpuFrame(
            "f",
            0,
            0,
            (1, 1),
            PixelFormat.NV12,
            (1, 1),
            "gpu0",
            (Plane(0, 1, 1),),
            resource,
            SyncToken("other", object()),
        )


def test_frame_metadata_is_immutable_snapshot() -> None:
    source = {"score": 1}
    value = GpuFrame(
        "f",
        0,
        0,
        (1, 1),
        PixelFormat.NV12,
        (1, 1),
        "gpu0",
        (Plane(0, 1, 1),),
        lease(),
        SyncToken("fake", object()),
        source,
    )
    source["score"] = 2
    assert value.metadata["score"] == 1
    with pytest.raises(TypeError):
        value.metadata["score"] = 3  # type: ignore[index]
