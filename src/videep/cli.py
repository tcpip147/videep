"""Videep 명령줄 진입점."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from pathlib import Path

from videep.algorithms.contracts import AlgorithmRole
from videep.algorithms.loader import load_algorithm
from videep.config import PipelineConfig
from videep.core.pipeline import PipelineResult, PipelineRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="videep")
    parser.add_argument("command", choices=("start", "stop", "status"))
    parser.add_argument("--config", type=Path)
    parser.add_argument(
        "--stats-interval",
        type=float,
        default=5.0,
        help="실행 중 통계 출력 주기(초). 0이면 비활성화합니다.",
    )
    return parser


async def _run_with_progress(runtime: PipelineRuntime, interval: float) -> PipelineResult:
    task = asyncio.create_task(runtime.run())
    if interval <= 0:
        return await task
    while not task.done():
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=interval)
        except TimeoutError:
            print(
                json.dumps({"event": "progress", **runtime.telemetry()}, ensure_ascii=False),
                flush=True,
            )
    return await task


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command in {"status", "stop"}:
        payload = {
            "state": "not-running",
            "message": "활성 프로세스 내부 런타임에만 중지 명령을 전달할 수 있습니다",
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    if args.config is None:
        raise SystemExit("start에는 --config가 필요합니다")
    config = PipelineConfig.from_mapping(json.loads(args.config.read_text(encoding="utf-8")))
    if config.backend != "nvidia":
        raise SystemExit(f"지원되지 않는 참조 백엔드: {config.backend}")
    from videep.backends.nvidia.backend import NvidiaBackend

    components = {
        role: load_algorithm(config.algorithms.reference_for(role.value), role)
        for role in AlgorithmRole
    }
    runtime = PipelineRuntime(config, NvidiaBackend(), components)
    result = asyncio.run(_run_with_progress(runtime, args.stats_interval))
    error = None
    if result.error is not None:
        causes = []
        current: BaseException | None = result.error
        while current is not None:
            causes.append(f"{type(current).__name__}: {current}")
            current = current.__cause__ or current.__context__
        error = " <- ".join(causes)
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "state": result.state.value,
                "frames_in": result.frames_in,
                "frames_out": result.frames_out,
                "error": error,
                "telemetry": runtime.telemetry(),
            },
            ensure_ascii=False,
        )
    )
    return 0 if result.error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
