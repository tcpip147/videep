# 구현 계획: 차량 분석 플러그인 예제

**브랜치**: `002-yolo-vehicle-plugin` | **작성일**: 2026-09-09 | **명세**: [spec.md](spec.md)

**입력**: `specs/002-yolo-vehicle-plugin/spec.md`의 기능 명세

## 요약

사용자가 복사하고 수정할 수 있는 차량 분석 예제를 추가한다. GPU 상주 NV12 프레임을 DLPack 무복사 보기로 가져와 YOLO 차량 검출과 차량 ROI 일괄 차급 분류를 실행하고, 소형·중형·대형 또는 미분류 결과를 경계 상자와 함께 GPU 프레임에 합성한다. 핵심 런타임에는 플러그인 단계 사이에서 런타임 소유의 메타데이터와 GPU 임시 산출물을 안전하게 전달하는 일반 계약만 추가하며, 모델 및 CUDA 구현은 예제에 격리한다.

## 기술 컨텍스트

**언어/버전**: Python 3.12 이상

**주요 의존성**: 기존 PyNvVideoCodec 2.2 계열, 선택적 PyTorch CUDA, torchvision, Ultralytics YOLO

**저장소**: 데이터베이스 없음. 사용자가 로컬에 제공하는 YOLO 가중치, 차급 분류 TorchScript 모델 및 JSON 설정 사용

**테스트**: pytest, pytest-asyncio, Ruff, mypy, 선택적 실제 NVIDIA GPU 통합·성능 테스트

**대상 플랫폼**: 기존 NVIDIA 백엔드가 동작하는 Windows 및 Linux x86-64. 예제는 NVIDIA 전용이지만 핵심 산출물 계약은 백엔드 독립적

**프로젝트 유형**: Python 라이브러리 및 CLI와 함께 제공되는 외부 플러그인 예제

**성능 목표**: 단일 1080p 스트림에서 목표 30fps를 설정 가능하게 유지하고 단계별 p50/p95 지연을 기록하며 30분 연속 실행에서 프레임 순서를 보존

**제약사항**: 전체 프레임 GPU→CPU→GPU 왕복 0회, `GpuFrame` 소유권 유지, 동일 CUDA 스트림 또는 이벤트 동기화, 검출·분류 메타데이터만 CPU 접근 허용, 프레임당 최대 차량 수 기본 32

**규모/범위**: 단일 스트림·GPU, 차량 검출 모델 1개와 차급 분류 모델 1개, 추적·번호판·모델 학습 제외

## 헌법 준수 검사

*관문: 0단계 연구 전에 통과했으며 1단계 설계 후 다시 검사했다.*

| 원칙 | 설계 준수 근거 | 결과 |
|---|---|---|
| I. GPU 상주 데이터 경로 | DLPack 무복사 보기와 CUDA 텐서 연산으로 전처리·추론·합성을 수행하고 CPU에는 작은 결과만 허용한다. | 통과 |
| II. 백엔드 독립성 | 핵심에는 불투명 산출물 계약만 추가하고 CUDA·모델 형식은 예제에 격리한다. | 통과 |
| III. `GpuFrame` 기본 모델 | 영상 픽셀의 기본 표현은 계속 `GpuFrame`이며 플러그인은 호출 범위의 `FrameView`만 사용한다. | 통과 |
| IV. 데이터/제어 평면 분리 | GPU 텐서는 프레임 데이터 경로, 좌표·레이블·측정값만 메타데이터 경로로 전달한다. | 통과 |
| V. 측정 가능한 성능 | 단계별 지연, 전송량, 메모리와 처리량을 자동·문서화된 시험으로 측정한다. | 통과 |
| VI. 사용자 알고리즘 런타임 | 전처리·추론·후처리를 별도 Python 모듈로 제공하고 런타임이 수명과 동기화를 소유한다. | 통과 |
| VII. 한글 명세 | 계획 및 설계 산출물을 한글로 작성한다. | 통과 |
| VIII. Python 표준 언어 | 공개 계약, 런타임 확장과 예제를 Python으로 구현한다. | 통과 |

설계 후 재검사에서도 모두 통과했다. 선택적 NVIDIA 예제 의존성은 핵심 패키지에서 분리되며 헌법 예외는 없다.

## 프로젝트 구조

### 이 기능의 문서

```text
specs/002-yolo-vehicle-plugin/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── artifact-contract.md
│   └── configuration-contract.md
├── checklists/requirements.md
└── tasks.md                 # $speckit-tasks 단계에서 생성
```

### 소스 코드

```text
src/videep/algorithms/
├── artifacts.py            # 단계 간 산출물, 수명 및 정리 계약
├── contracts.py            # 하위 호환 플러그인 계약
└── view.py                 # FrameView와 산출물 접근
src/videep/core/pipeline.py # 프레임별 저장소 생성·전달·정리

examples/yolo_vehicle/
├── README.md
├── config.example.json
├── pipeline.example.json
├── preprocess.py
├── inference.py
├── postprocess.py
├── models.py
├── kernels.py
└── labels.py

tests/
├── contract/test_algorithm_artifacts.py
├── contract/test_yolo_vehicle_contract.py
├── integration/test_yolo_vehicle_pipeline.py
├── performance/test_yolo_vehicle_zero_copy.py
└── unit/
    ├── test_vehicle_config.py
    ├── test_vehicle_postprocess.py
    └── test_vehicle_results.py
```

**구조 결정**: 기존 단일 패키지를 유지한다. 재사용 가능한 산출물 계약만 핵심에 배치하고 모델별 코드와 선택적 GPU 의존성은 `examples/yolo_vehicle`에 격리한다. 모델 파일은 저장소에 포함하지 않는다.

## 구현 접근

### 1. 단계 간 산출물 계약

- 런타임은 각 프레임마다 `FrameArtifacts`를 생성해 세 플러그인에 같은 인스턴스를 제공한다.
- 계약 1.0의 `process(frame_view)`는 그대로 지원하고 계약 1.1은 `process(frame_view, artifacts)`를 사용한다.
- 작은 불변 메타데이터와 플러그인이 할당한 GPU 산출물을 구분한다.
- GPU 산출물은 백엔드·장치·생성 단계·준비 이벤트·해제 콜백을 기록하며 런타임이 오류를 포함한 모든 경로에서 한 번 정리한다.
- 기반 `GpuFrame` 핸들 또는 lease는 산출물로 등록할 수 없다.

### 2. GPU 전처리

- `torch.from_dlpack(FrameView)`로 같은 GPU 메모리를 공유하며 프레임 수명 안에서만 텐서를 사용한다.
- 파이프라인 CUDA 스트림에서 NV12→RGB, 레터박스 크기 조정, 정규화와 NCHW 배치를 수행한다.
- 검출 입력 텐서와 원본 좌표 복원 정보를 산출물로 등록한다.

### 3. 차량 검출 및 차급 분류

- 초기화 시 YOLO 모델과 차급 TorchScript 모델을 한 번 로드하고 장치·입출력·레이블을 검증하며 준비 실행한다.
- GPU 텐서를 YOLO 입력으로 전달하고 검출 결과를 GPU에 유지한다.
- 대상 종류 필터링과 중복 억제를 GPU에서 수행한 뒤 상위 결과만 선택한다.
- `roi_align`으로 차량 영역을 GPU 배치 텐서로 만들고 차급 모델을 한 번 실행한다.
- 검출과 차급 결과는 안정적인 `detection_id`로 연결한다.

### 4. GPU 표시

- 후처리는 검출·차급 결과로 경계 상자와 레이블을 writable GPU 프레임에 합성한다.
- 런타임은 입력을 수정할 수 있는지 명시하거나 별도의 writable 출력 `GpuFrame`을 제공한다.
- 네 개의 고정 레이블과 숫자는 초기화 시 GPU에 올린 비트맵 glyph atlas로 렌더링한다.
- 완료 이벤트를 기록하고 장치 전체 동기화나 전체 프레임 CPU 접근을 사용하지 않는다.

### 5. 설정·오류·계측

- 예제 JSON 설정을 초기화 시 엄격히 검증한다.
- 모델 누락, 장치 불일치, 형상, DLPack, 스트림, writable 출력과 메모리 오류에 단계 정보를 포함한다.
- 차량 수, 미분류 수, 단계별 GPU 시간, 버퍼 사용량과 CPU 전송량을 측정한다.
- 정상·오류·취소 종료에서 모델, GPU 텐서 및 산출물 해제를 검증한다.

## 복잡성 추적

헌법 위반이 없으므로 별도 정당화가 필요한 복잡성은 없다.

