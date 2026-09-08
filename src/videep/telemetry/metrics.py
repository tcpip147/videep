"""백엔드 중립 파이프라인 메트릭."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from math import ceil

SAFE_LABELS = frozenset({"run_id", "stage", "backend", "device"})


def percentile(values: Iterable[float], quantile: float) -> float:
    samples = sorted(values)
    if not samples:
        return 0.0
    if not 0 <= quantile <= 1:
        raise ValueError("quantile은 0과 1 사이여야 합니다")
    return samples[max(0, ceil(quantile * len(samples)) - 1)]


@dataclass(slots=True)
class MetricsRegistry:
    labels: Mapping[str, str]
    counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    gauges: dict[str, float] = field(default_factory=dict)
    samples: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def __post_init__(self) -> None:
        unsafe = set(self.labels) - SAFE_LABELS
        if unsafe:
            raise ValueError(f"안전하지 않은 메트릭 라벨: {sorted(unsafe)}")

    def increment(self, name: str, amount: int = 1) -> None:
        self.counters[name] += amount

    def set_gauge(self, name: str, value: float) -> None:
        self.gauges[name] = value

    def observe(self, name: str, value: float) -> None:
        self.samples[name].append(value)

    def summary(self, name: str) -> dict[str, float]:
        values = self.samples.get(name, [])
        return {
            "p50": percentile(values, 0.50),
            "p95": percentile(values, 0.95),
            "p99": percentile(values, 0.99),
        }

    def snapshot(self) -> dict[str, object]:
        """Return JSON-safe counters, gauges and latency percentiles."""

        return {
            **dict(self.counters),
            **dict(self.gauges),
            **{
                f"{name}_{key}": value
                for name in self.samples
                for key, value in self.summary(name).items()
            },
        }


def record_vehicle_analysis(
    registry: object | None, analysis: Iterable[Mapping[str, object]]
) -> None:
    """Record bounded vehicle metadata without coupling plugins to the registry class."""

    if registry is None or not hasattr(registry, "increment"):
        return
    items = tuple(analysis)
    increment = registry.increment
    increment("vehicles_detected", len(items))
    increment("vehicles_unclassified", sum(item.get("size") == "미분류" for item in items))
