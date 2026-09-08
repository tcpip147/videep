# 차량 분석 플러그인 예제 검증 기록

## 2026-09-09 자동 검증

- `ruff check src examples tests`: 통과
- `mypy src examples`: 통과(40개 소스 파일)
- `pytest`: 70개 통과, 9개 GPU·성능 선택 실행 테스트 제외
- 계약 1.0 플러그인의 기존 호출 방식과 계약 1.1의 `FrameArtifacts` 호출 방식을 함께 검증했다.
- 예제 데이터 경로에서 `.cpu()`, `.numpy()`, `np.asarray`를 사용하지 않음을 정적 검사했다.
- 가짜 차량 결과를 사용한 차량 있음·없음·가림, 프레임 순서, 설정 교체 및 표시 경계 테스트를 통과했다.
- 런타임 텔레메트리에 차량 수, 미분류 수 및 단계별 p50/p95/p99 처리 시간을 연결했다.

## 실제 GPU 검증 대기 항목

다음 항목은 실제 YOLO 모델, 3종 차량 분류 TorchScript 모델, NVIDIA CUDA 환경 및 시험 RTSP 스트림이 있어야 실행할 수 있다.

- 실제 프레임의 차량 검출·분류 정확성 및 NV12 오버레이 확인
- GPU/CPU 전송량, 단계별 p50/p95 지연, 처리량 및 GPU 메모리 측정
- 30분 연속 실행 중 프레임 순서, 메모리 증가, 아티팩트 누수 및 파이프라인 중단 확인

모델 파일은 저장소에 포함하지 않으며 `examples/yolo_vehicle/models/`에 배치한다. 실행 절차와 설정 항목은 `examples/yolo_vehicle/README.md` 및 예제 JSON을 따른다.

실제 GPU 통합 검증 시 `VIDEEP_VEHICLE_PIPELINE_CONFIG`에 실사용 설정 파일을 지정한 뒤 다음 명령을 실행한다.

```powershell
$env:VIDEEP_VEHICLE_PIPELINE_CONFIG = "examples/yolo_vehicle/pipeline.json"
.venv\Scripts\python.exe -m pytest tests\integration\test_yolo_vehicle_pipeline.py --run-gpu -q
.venv\Scripts\python.exe -m pytest tests\performance\test_yolo_vehicle_zero_copy.py --run-gpu --run-performance -q
```

30분 검증 시간은 기본 1800초이며, 빠른 사전 점검에서는 `VIDEEP_SOAK_SECONDS`로 줄일 수 있다. 측정 JSON은 pytest의 `performance_artifact_dir`에 기록된다.
