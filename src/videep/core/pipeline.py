"""단일 스트림 GPU 파이프라인 실행기."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from time import perf_counter
from uuid import uuid4

from videep.algorithms.artifacts import FrameArtifacts
from videep.algorithms.contracts import (
    AlgorithmComponent,
    AlgorithmContext,
    AlgorithmRole,
    contract_minor,
)
from videep.algorithms.view import scoped_frame_view
from videep.backends.base import Backend
from videep.config import PipelineConfig
from videep.control.events import ControlEvent, EventKind
from videep.core.capabilities import CapabilitySet, negotiate
from videep.core.frame import GpuFrame
from videep.core.queue import EOS, FrameQueue, SignalKind, StreamSignal
from videep.telemetry.metrics import MetricsRegistry


class RunState(StrEnum):
    CREATED = "created"
    VALIDATING = "validating"
    READY = "ready"
    RUNNING = "running"
    DRAINING = "draining"
    STOPPING = "stopping"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(slots=True)
class PipelineResult:
    run_id: str
    state: RunState
    frames_in: int
    frames_out: int
    error: BaseException | None = None


class PipelineRuntime:
    """리소스 소유권을 유지하며 한 입력 스트림을 처리한다."""

    def __init__(
        self,
        config: PipelineConfig,
        backend: Backend,
        algorithms: Mapping[AlgorithmRole, AlgorithmComponent],
        *,
        event_sink: Callable[[ControlEvent], None] | None = None,
    ) -> None:
        self.config = config
        self.backend = backend
        self.algorithms = algorithms
        self.run_id = uuid4().hex
        self.state = RunState.CREATED
        self.metrics = MetricsRegistry(
            {"run_id": self.run_id, "backend": backend.backend_id, "device": config.device_id}
        )
        self._event_sink = event_sink
        self._stop = asyncio.Event()

    def request_stop(self) -> None:
        self._stop.set()

    def telemetry(self) -> dict[str, object]:
        """실행 중에도 안전하게 읽을 수 있는 진행 상태 스냅샷을 반환한다."""
        return {
            "run_id": self.run_id,
            "state": self.state.value,
            **self.metrics.snapshot(),
        }

    def _emit(self, kind: EventKind, payload: dict[str, object]) -> None:
        if self._event_sink:
            self._event_sink(ControlEvent(kind, self.run_id, payload))

    def _set_state(self, state: RunState) -> None:
        self.state = state
        self._emit(EventKind.STATE, {"state": state.value})

    def _validate(self) -> CapabilitySet:
        self._set_state(RunState.VALIDATING)
        devices = {item.device_id: item for item in self.backend.enumerate_devices()}
        if self.config.device_id not in devices:
            raise ValueError(f"GPU 장치를 찾을 수 없습니다: {self.config.device_id}")
        capability = CapabilitySet.from_device(devices[self.config.device_id])
        negotiated = negotiate([capability])
        for role in AlgorithmRole:
            component = self.algorithms[role]
            if AlgorithmRole(component.role) is not role:
                raise ValueError(f"알고리즘 역할 불일치: {role.value}")
            component.validate(negotiated)
        self._set_state(RunState.READY)
        return negotiated

    async def run(self) -> PipelineResult:
        frames_in = frames_out = 0
        pool = decoder = encoder = None
        try:
            capability = self._validate()
            pool = self.backend.create_pool(self.config.device_id, self._capacity("decode"))
            synchronizer = self.backend.create_synchronizer(self.config.device_id)
            stream = getattr(synchronizer, "stream", 0)
            # GPU plugins (PyTorch, CuPy, etc.) must establish the device's primary
            # CUDA context before NVDEC/NVENC objects capture a CUDA context.
            for role, component in self.algorithms.items():
                component.initialize(
                    AlgorithmContext(
                        self.backend.backend_id,
                        self.config.device_id,
                        stream,
                        capability,
                        self.config.algorithms.options_for(role.value),
                        self.metrics,
                    )
                )
            decoder = self.backend.create_decoder(self.config.input_uri, pool)
            encoder = self.backend.create_encoder(self.config.output_uri, self.config.device_id)
            self._set_state(RunState.RUNNING)

            artifacts_by_frame: dict[str, FrameArtifacts] = {}

            queues = [
                FrameQueue[GpuFrame](self._capacity(name))
                for name in ("preprocess", "inference", "postprocess", "encode")
            ]

            async def produce() -> None:
                nonlocal frames_in
                async for frame in decoder:
                    if self._stop.is_set():
                        break
                    frame.resource_lease.transfer(frame.resource_lease.owner, "preprocess")
                    artifacts_by_frame[frame.frame_id] = FrameArtifacts(
                        frame.frame_id, self.backend.backend_id, self.config.device_id
                    )
                    await queues[0].put(frame)
                    frames_in += 1
                    self.metrics.increment("frames_in")
                await queues[0].put(EOS)

            async def process(index: int, role: AlgorithmRole, owner: str, next_owner: str) -> None:
                component = self.algorithms[role]
                source, target = queues[index], queues[index + 1]
                while True:
                    item = await source.get()
                    if isinstance(item, StreamSignal):
                        await target.put(item)
                        return
                    await synchronizer.wait(item.sync_token, consumer_stream=stream)
                    artifacts = artifacts_by_frame[item.frame_id]
                    with (
                        item.resource_lease.borrow_view(owner) as borrowed,
                        scoped_frame_view(
                            borrowed.resource,
                            consumer_stream=stream,
                            frame_id=item.frame_id,
                            metadata=item.metadata,
                            writable=item.writable,
                        ) as view,
                    ):
                        started = perf_counter()
                        result = (
                            component.process(view, artifacts)
                            if contract_minor(component.contract_version) >= 1
                            else component.process(view)
                        )
                        if inspect.isawaitable(result):
                            await result
                        self.metrics.observe(
                            f"{role.value}_stage_seconds", perf_counter() - started
                        )
                    item.resource_lease.transfer(owner, next_owner)
                    await target.put(item)
                    self.metrics.increment(f"frames_{role.value}")

            async def consume() -> None:
                nonlocal frames_out
                while True:
                    item = await queues[-1].get()
                    if isinstance(item, StreamSignal):
                        if item.kind is SignalKind.ERROR:
                            raise item.error or RuntimeError("알 수 없는 데이터 플레인 오류")
                        return
                    await encoder.encode(item)
                    frames_out += 1
                    self.metrics.increment("frames_out")
                    telemetry = getattr(encoder, "telemetry", None)
                    if callable(telemetry):
                        for name, value in telemetry().items():
                            self.metrics.set_gauge(name, float(value))
                    artifacts_by_frame.pop(item.frame_id).close()

            await asyncio.gather(
                produce(),
                process(0, AlgorithmRole.PREPROCESS, "preprocess", "inference"),
                process(1, AlgorithmRole.INFERENCE, "inference", "postprocess"),
                process(2, AlgorithmRole.POSTPROCESS, "postprocess", "encoder"),
                consume(),
            )
            self._set_state(RunState.STOPPING if self._stop.is_set() else RunState.DRAINING)
            final = RunState.STOPPED if self._stop.is_set() else RunState.COMPLETED
            self._set_state(final)
            return PipelineResult(self.run_id, final, frames_in, frames_out)
        except BaseException as exc:
            self._set_state(RunState.FAILED)
            self._emit(EventKind.ERROR, {"type": type(exc).__name__, "message": str(exc)})
            return PipelineResult(self.run_id, self.state, frames_in, frames_out, exc)
        finally:
            if "artifacts_by_frame" in locals():
                for artifacts in artifacts_by_frame.values():
                    with suppress(Exception):
                        artifacts.close()
            for component in self.algorithms.values():
                with suppress(Exception):
                    component.close()
            for resource in (decoder, encoder, pool):
                if resource is not None:
                    with suppress(Exception):
                        await resource.close()

    def _capacity(self, stage: str) -> int:
        capacity = self.config.queue_capacity
        if isinstance(capacity, Mapping):
            return capacity.get(stage, 4)
        return capacity
