"""NVIDIA 백엔드 계측 어댑터."""

from dataclasses import dataclass
from time import perf_counter_ns


@dataclass(slots=True)
class NvidiaTelemetry:
    host_to_device_full_frame: int = 0
    device_to_host_full_frame: int = 0
    peak_gpu_memory_bytes: int = 0

    def begin_gpu_event(self) -> int:
        return perf_counter_ns()

    def end_gpu_event_ms(self, started_ns: int) -> float:
        return (perf_counter_ns() - started_ns) / 1_000_000

    def record_full_frame_transfer(self, direction: str) -> None:
        if direction == "host-to-device":
            self.host_to_device_full_frame += 1
        elif direction == "device-to-host":
            self.device_to_host_full_frame += 1
        else:
            raise ValueError(f"알 수 없는 전송 방향: {direction}")

    @property
    def zero_copy_proven(self) -> bool:
        return self.host_to_device_full_frame == self.device_to_host_full_frame == 0
