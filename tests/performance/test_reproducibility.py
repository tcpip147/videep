import pytest

from videep.telemetry.benchmark import BenchmarkRecord


def record(
    environment: str = "env", throughput: float = 100.0, latency: float = 10.0
) -> BenchmarkRecord:
    return BenchmarkRecord("input", "config", environment, throughput, latency, 1024, 4)


def test_regression_thresholds() -> None:
    baseline = record()
    assert record(throughput=94.0).regression_against(baseline)["throughput"]
    assert record(latency=10.6).regression_against(baseline)["p95_latency"]
    assert not any(record(throughput=96.0, latency=10.4).regression_against(baseline).values())


def test_fingerprint_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError):
        record(environment="other").regression_against(record())
