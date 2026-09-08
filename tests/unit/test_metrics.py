import pytest

from videep.telemetry.metrics import MetricsRegistry, percentile, record_vehicle_analysis


def test_percentiles_and_counters() -> None:
    registry = MetricsRegistry({"run_id": "r1", "stage": "decode"})
    registry.increment("frames_in")
    for value in range(1, 101):
        registry.observe("latency_ms", float(value))
    assert registry.counters["frames_in"] == 1
    assert registry.summary("latency_ms") == {"p50": 50.0, "p95": 95.0, "p99": 99.0}
    assert percentile([], 0.95) == 0.0


def test_unsafe_labels_are_rejected() -> None:
    with pytest.raises(ValueError):
        MetricsRegistry({"pixels": "secret"})


def test_vehicle_analysis_and_latency_are_exposed_in_snapshot() -> None:
    registry = MetricsRegistry({"run_id": "r1"})
    record_vehicle_analysis(registry, ({"size": "소형"}, {"size": "미분류"}))
    registry.observe("inference_stage_seconds", 0.01)

    snapshot = registry.snapshot()
    assert snapshot["vehicles_detected"] == 2
    assert snapshot["vehicles_unclassified"] == 1
    assert snapshot["inference_stage_seconds_p95"] == 0.01
