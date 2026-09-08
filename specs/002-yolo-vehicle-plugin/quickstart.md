# 빠른 시작 및 검증 가이드

## 사전 조건

- Python 3.12 이상과 기존 NVIDIA 백엔드가 동작하는 GPU 환경
- CUDA에서 실행 가능한 YOLO 차량 검출 가중치
- 소형·중형·대형 순서의 TorchScript 차급 분류 모델
- 자동차가 포함된 H264 입력

모델 파일은 저장소에 포함되지 않으며 [설정 계약](contracts/configuration-contract.md)을 따라 사용자가 준비한다.

## 선택적 의존성

```powershell
uv sync --extra dev --extra nvidia --extra vehicle-example
.venv\Scripts\python.exe -c "import torch, torchvision, ultralytics; print(torch.cuda.is_available())"
```

## 설정 준비

```powershell
Copy-Item examples\yolo_vehicle\config.example.json examples\yolo_vehicle\config.json
Copy-Item examples\yolo_vehicle\pipeline.example.json examples\yolo_vehicle\pipeline.json
```

두 파일에서 모델 경로, GPU 장치와 입력·출력 URI를 실제 환경에 맞게 변경한다.

## 계약 및 단위 검증

```powershell
.venv\Scripts\python.exe -m pytest tests\contract\test_algorithm_artifacts.py tests\contract\test_yolo_vehicle_contract.py tests\unit\test_vehicle_config.py tests\unit\test_vehicle_results.py -q
```

기존 계약 1.0 호환, 프레임별 격리, 오류 시 단일 정리와 잘못된 설정의 사전 거부를 확인한다.

## 실제 GPU 실행

```powershell
.venv\Scripts\python.exe -m pytest tests\integration\test_yolo_vehicle_pipeline.py --run-gpu -q
.venv\Scripts\python.exe -m videep.cli start --config examples\yolo_vehicle\pipeline.json --stats-interval 5
```

자동차별 경계 상자와 소형·중형·대형 또는 미분류 레이블이 표시되고, 자동차가 없는 프레임도 순서대로 출력되어야 한다.

## 무복사 및 성능 검증

```powershell
.venv\Scripts\python.exe -m pytest tests\performance\test_yolo_vehicle_zero_copy.py --run-gpu --run-performance -q
```

전체 프레임 GPU→CPU→GPU 왕복 0회, 제한된 결과 메타데이터만 CPU 전송, 단계별 p50/p95 시간과 메모리 사용량 및 30분 연속 자원 안정성을 확인한다.

## 실패 경로

존재하지 않는 모델, 다른 장치, 범위를 벗어난 임계값, 지원되지 않는 프레임 형식과 writable 출력 부재를 각각 시험한다. 오류에는 단계, 대상과 해결 방향이 포함되고 할당된 GPU 자원은 모두 반환되어야 한다.

