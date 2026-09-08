"""GPU-resident YOLO vehicle detection plugin."""

from __future__ import annotations

from typing import Any, cast

from videep.algorithms.artifacts import FrameArtifacts
from videep.algorithms.contracts import AlgorithmContext, AlgorithmRole
from videep.algorithms.view import FrameView

from .models import VehicleAnalysisResult, VehicleConfig, VehicleDetection, config_from_options


def _libraries() -> tuple[Any, Any]:
    try:
        import torch
        from ultralytics import YOLO  # type: ignore[attr-defined]
    except ImportError as exc:
        raise RuntimeError(
            "[detection] dependencies: torch와 ultralytics를 설치해야 합니다"
        ) from exc
    return torch, YOLO


class Plugin:
    role = AlgorithmRole.INFERENCE
    contract_version = "1.1"

    def validate(self, capabilities: object) -> None:
        del capabilities

    def initialize(self, context: AlgorithmContext) -> None:
        self.context = context
        self.config: VehicleConfig = config_from_options(context.options)
        if context.backend_id != "nvidia" or context.device_id != self.config.device_id:
            raise RuntimeError("[detection] device_id: 파이프라인과 설정의 GPU 장치가 다릅니다")
        torch, yolo = _libraries()
        if not torch.cuda.is_available():
            raise RuntimeError("[detection] CUDA: 사용 가능한 CUDA 장치가 없습니다")
        self._torch = torch
        self._device = torch.device(f"cuda:{self.config.device_id}")
        self._detector = yolo(str(self.config.detector_model))
        self._tracks: dict[int, tuple[VehicleDetection, int]] = {}
        self._next_track_id = 0

    def process(self, frame_view: FrameView, artifacts: FrameArtifacts) -> None:
        tensor: Any = artifacts.get_gpu("vehicle.detector_input", self.role.value).value
        scale, pad_x, pad_y = cast(
            tuple[float, int, int], artifacts.get_metadata("vehicle.letterbox", tuple)
        )
        detections: list[VehicleDetection] = []
        with self._torch.inference_mode():
            results = self._detector.predict(
                source=tensor,
                conf=self.config.detection_confidence,
                iou=self.config.iou_threshold,
                max_det=self.config.max_vehicles,
                verbose=False,
                device=self._device,
            )
            boxes = results[0].boxes
            if boxes is not None:
                names = results[0].names
                for class_id, confidence, box in zip(
                    boxes.cls.to(dtype=self._torch.int64).tolist(),
                    boxes.conf.tolist(),
                    boxes.xyxy.tolist(),
                    strict=True,
                ):
                    object_class = str(names[int(class_id)])
                    if object_class not in self.config.target_classes:
                        continue
                    x1, y1, x2, y2 = box
                    detection = VehicleDetection(
                        len(detections),
                        (x1 - pad_x) / scale,
                        (y1 - pad_y) / scale,
                        (x2 - pad_x) / scale,
                        (y2 - pad_y) / scale,
                        object_class,
                        float(confidence),
                    ).clipped(
                        round((tensor.shape[3] - 2 * pad_x) / scale),
                        round((tensor.shape[2] - 2 * pad_y) / scale),
                    )
                    if detection.x1 < detection.x2 and detection.y1 < detection.y2:
                        detection.validate()
                        detections.append(detection)
        detections = self._stabilize(detections)
        result = VehicleAnalysisResult(frame_view.frame_id or artifacts.frame_id, tuple(detections))
        result.validate()
        artifacts.put_metadata("vehicle.analysis", result.as_metadata())

    def close(self) -> None:
        self._detector = None
        self._tracks.clear()

    def _stabilize(self, detections: list[VehicleDetection]) -> list[VehicleDetection]:
        """Smooth boxes and retain tracks through brief detector misses."""

        unmatched = set(range(len(detections)))
        updated: dict[int, tuple[VehicleDetection, int]] = {}
        output: list[VehicleDetection] = []
        for track_id, (previous, missed) in self._tracks.items():
            candidates = [
                index
                for index in unmatched
                if detections[index].object_class == previous.object_class
            ]
            best = max(
                candidates, key=lambda index: _box_iou(previous, detections[index]), default=None
            )
            if best is not None and _box_iou(previous, detections[best]) >= 0.3:
                current = detections[best]
                unmatched.remove(best)
                alpha = 0.65
                stable = VehicleDetection(
                    track_id,
                    previous.x1 * (1 - alpha) + current.x1 * alpha,
                    previous.y1 * (1 - alpha) + current.y1 * alpha,
                    previous.x2 * (1 - alpha) + current.x2 * alpha,
                    previous.y2 * (1 - alpha) + current.y2 * alpha,
                    current.object_class,
                    current.confidence,
                )
                updated[track_id] = (stable, 0)
                output.append(stable)
            elif missed < 4:
                updated[track_id] = (previous, missed + 1)
                output.append(previous)
        for index in unmatched:
            current = detections[index]
            stable = VehicleDetection(
                self._next_track_id,
                current.x1,
                current.y1,
                current.x2,
                current.y2,
                current.object_class,
                current.confidence,
            )
            updated[self._next_track_id] = (stable, 0)
            output.append(stable)
            self._next_track_id += 1
        self._tracks = updated
        return output


def _box_iou(left: VehicleDetection, right: VehicleDetection) -> float:
    intersection_width = max(0.0, min(left.x2, right.x2) - max(left.x1, right.x1))
    intersection_height = max(0.0, min(left.y2, right.y2) - max(left.y1, right.y1))
    intersection = intersection_width * intersection_height
    left_area = (left.x2 - left.x1) * (left.y2 - left.y1)
    right_area = (right.x2 - right.x1) * (right.y2 - right.y1)
    union = left_area + right_area - intersection
    return intersection / union if union > 0 else 0.0
