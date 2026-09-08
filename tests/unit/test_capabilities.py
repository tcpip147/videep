from __future__ import annotations

import pytest

from videep.core.capabilities import (
    CapabilitySet,
    DeviceCapability,
    PixelFormat,
    PlaneLayout,
    negotiate,
)


def capability(
    device: str = "gpu0", formats: frozenset[PixelFormat] | None = None
) -> CapabilitySet:
    return CapabilitySet.from_device(
        DeviceCapability(
            backend_id="fake",
            device_id=device,
            codecs=frozenset({"h264"}),
            pixel_formats=formats or frozenset({PixelFormat.NV12}),
            plane_layouts=frozenset({PlaneLayout.PITCH_LINEAR}),
            external_handle_types=frozenset({"opaque"}),
            synchronization_types=frozenset({"timeline"}),
            zero_copy_interop=frozenset({"dlpack"}),
        )
    )


def test_capability_intersection_preserves_common_zero_copy_path() -> None:
    result = negotiate(
        (capability(), capability(formats=frozenset({PixelFormat.NV12, PixelFormat.P010})))
    )
    assert result.devices == frozenset({"gpu0"})
    assert result.pixel_formats == frozenset({PixelFormat.NV12})
    assert result.supports_zero_copy()


def test_device_mismatch_fails_negotiation() -> None:
    with pytest.raises(ValueError, match="무복사"):
        negotiate((capability("gpu0"), capability("gpu1")))


def test_missing_zero_copy_interop_fails_negotiation() -> None:
    broken = CapabilitySet(
        devices=frozenset({"gpu0"}),
        codecs=frozenset({"h264"}),
        pixel_formats=frozenset({PixelFormat.NV12}),
        plane_layouts=frozenset({PlaneLayout.PITCH_LINEAR}),
        external_handle_types=frozenset({"opaque"}),
        synchronization_types=frozenset({"timeline"}),
        zero_copy_interop=frozenset(),
    )
    with pytest.raises(ValueError, match="무복사"):
        negotiate((capability(), broken))
