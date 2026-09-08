from __future__ import annotations

from types import SimpleNamespace

import pytest

from videep.backends.base import Backend, Decoder, Encoder, ResourcePool
from videep.backends.nvidia.backend import NvidiaBackend
from videep.core.sync import Synchronizer


class FakeSdk:
    def allocate_gpu_resource(self, size: int):  # type: ignore[no-untyped-def]
        from videep.backends.nvidia.interop import NvidiaResource

        return NvidiaResource(object(), "0", size)

    def create_decode_driver(self, device_id: str) -> object:
        return SimpleNamespace(decode=lambda source: (), close=lambda: None)

    def create_encode_driver(self, output_uri: str, device_id: str) -> object:
        return SimpleNamespace(
            encode_gpu=lambda resource, frame: None,
            flush=lambda: None,
            close=lambda: None,
        )


def test_nvidia_backend_implements_public_backend_contract() -> None:
    backend = NvidiaBackend(sdk=FakeSdk())  # type: ignore[arg-type]
    pool = backend.create_pool("0", 4)

    assert isinstance(backend, Backend)
    assert isinstance(pool, ResourcePool)
    assert isinstance(backend.create_decoder("input.mp4", pool), Decoder)
    assert isinstance(backend.create_encoder("output.mp4", "0"), Encoder)
    assert isinstance(backend.create_synchronizer("0"), Synchronizer)


def test_capabilities_describe_zero_copy_transport() -> None:
    capability = NvidiaBackend(sdk=FakeSdk()).enumerate_devices()[0]  # type: ignore[arg-type]

    assert capability.backend_id == "nvidia"
    assert "dlpack" in capability.zero_copy_interop
    assert "cuda-event" in capability.synchronization_types
    assert "cuda-device-pointer" in capability.external_handle_types


@pytest.mark.gpu
def test_installed_nvidia_sdk_can_be_discovered() -> None:
    if not NvidiaBackend.available():
        pytest.skip("PyNvVideoCodec is not installed")
    assert NvidiaBackend().enumerate_devices()
