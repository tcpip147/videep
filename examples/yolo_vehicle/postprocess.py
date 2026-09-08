"""검출 경계 상자와 차급을 GPU 프레임에 표시하는 후처리 플러그인."""

from __future__ import annotations

from videep.algorithms.artifacts import FrameArtifacts
from videep.algorithms.contracts import AlgorithmContext, AlgorithmRole
from videep.algorithms.view import FrameView
from videep.telemetry.metrics import record_vehicle_analysis

from .kernels import draw_overlay
from .models import VehicleConfig, config_from_options


class Plugin:
    role = AlgorithmRole.POSTPROCESS
    contract_version = "1.1"

    def validate(self, capabilities: object) -> None:
        del capabilities

    def initialize(self, context: AlgorithmContext) -> None:
        self.context = context
        self.config: VehicleConfig = config_from_options(context.options)
        if context.backend_id != "nvidia" or context.device_id != self.config.device_id:
            raise RuntimeError("[overlay] device_id: NVIDIA 파이프라인 장치와 같아야 합니다")

    def process(self, frame_view: FrameView, artifacts: FrameArtifacts) -> None:
        analysis = artifacts.get_metadata("vehicle.analysis", tuple)
        draw_overlay(
            frame_view,
            analysis,  # type: ignore[arg-type]
            writable=frame_view.writable,
            colors=self.config.box_colors,
        )
        record_vehicle_analysis(self.context.metrics, analysis)  # type: ignore[arg-type]
        artifacts.put_metadata("vehicle.overlay_ready", True)

    def close(self) -> None:
        pass
