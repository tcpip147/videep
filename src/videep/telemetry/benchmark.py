"""재현 가능한 벤치마크 결과 모델과 비교."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def fingerprint(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(slots=True)
class BenchmarkRecord:
    input_fingerprint: str
    config_fingerprint: str
    environment_fingerprint: str
    throughput_fps: float
    p95_latency_ms: float
    peak_gpu_memory_bytes: int
    queue_high_watermark: int
    host_to_device_full_frame: int = 0
    device_to_host_full_frame: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    def comparable_to(self, other: "BenchmarkRecord") -> bool:
        return (
            self.input_fingerprint,
            self.config_fingerprint,
            self.environment_fingerprint,
        ) == (
            other.input_fingerprint,
            other.config_fingerprint,
            other.environment_fingerprint,
        )

    def regression_against(
        self, baseline: "BenchmarkRecord", tolerance: float = 0.05
    ) -> dict[str, bool]:
        if not self.comparable_to(baseline):
            raise ValueError("서로 다른 입력, 구성 또는 환경의 결과는 비교할 수 없습니다")
        return {
            "throughput": self.throughput_fps < baseline.throughput_fps * (1 - tolerance),
            "p95_latency": self.p95_latency_ms > baseline.p95_latency_ms * (1 + tolerance),
        }
