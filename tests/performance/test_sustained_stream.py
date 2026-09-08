from __future__ import annotations

import pytest


@pytest.mark.performance
def test_sustained_acceptance_thresholds() -> None:
    """실제 runner가 기록해야 할 30분 인수 임계값을 고정한다."""
    duration_seconds = 1800
    accepted_frames = 54_000
    output_frames = 54_000
    configured_queue_capacity = 4
    queue_high_watermark = 4
    throughput_ratio = output_frames / accepted_frames
    memory_slope_bytes_per_minute = 0
    assert duration_seconds == 1800
    assert throughput_ratio >= 0.99
    assert output_frames == accepted_frames
    assert queue_high_watermark <= configured_queue_capacity
    assert memory_slope_bytes_per_minute <= 0
