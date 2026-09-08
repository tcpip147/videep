"""YOLO 차량 예제 전처리 플러그인."""

from __future__ import annotations

from videep.algorithms.artifacts import FrameArtifacts, GpuArtifact
from videep.algorithms.contracts import AlgorithmContext, AlgorithmRole
from videep.algorithms.view import FrameView

from .kernels import nv12_to_detector_input
from .models import VehicleConfig, config_from_options


class Plugin:
    role = AlgorithmRole.PREPROCESS
    contract_version = "1.1"

    def validate(self, capabilities: object) -> None:
        del capabilities

    def initialize(self, context: AlgorithmContext) -> None:
        self.context = context
        self.config: VehicleConfig = config_from_options(context.options)
        if context.backend_id != "nvidia" or context.device_id != self.config.device_id:
            raise RuntimeError("[preprocess] device_id: NVIDIA 파이프라인 장치와 같아야 합니다")

    def process(self, frame_view: FrameView, artifacts: FrameArtifacts) -> None:
        detector_input, letterbox = nv12_to_detector_input(frame_view)
        artifacts.put_gpu(
            "vehicle.detector_input",
            GpuArtifact(
                detector_input,
                self.context.backend_id,
                self.context.device_id,
                self.role.value,
            ),
        )
        artifacts.put_metadata("vehicle.letterbox", letterbox)

    def close(self) -> None:
        pass
