# 작업 목록: 차량 분석 플러그인 예제

**입력**: `specs/002-yolo-vehicle-plugin/`의 설계 문서

**필수 문서**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**테스트 원칙**: 명세의 무복사, 정확성, 오류 보고 및 30분 연속 실행 성공 기준을 검증하기 위해 계약·단위·통합·성능 테스트를 포함한다. 각 사용자 스토리의 테스트를 구현보다 먼저 작성하고 실패를 확인한다.

**구성 원칙**: 각 사용자 스토리를 독립적으로 구현하고 검증할 수 있도록 단계별로 작업을 묶는다.

## 형식: `[ID] [P?] [Story] 설명과 파일 경로`

- **[P]**: 미완료 작업과 파일 충돌 없이 병렬 수행 가능
- **[Story]**: 사용자 스토리 연결 표시
- 모든 작업은 구체적인 파일 경로를 포함

## 1단계: 준비

**목적**: 선택적 차량 예제 패키지와 디렉터리 골격 준비

- [X] T001 `examples/yolo_vehicle/__init__.py`, `examples/yolo_vehicle/preprocess.py`, `examples/yolo_vehicle/inference.py`, `examples/yolo_vehicle/postprocess.py`, `examples/yolo_vehicle/models.py`, `examples/yolo_vehicle/kernels.py`, `examples/yolo_vehicle/labels.py`에 차량 예제 모듈 골격 생성
- [X] T002 [P] PyTorch CUDA, torchvision 및 Ultralytics를 핵심 의존성과 분리된 `vehicle-example` 선택 항목으로 `pyproject.toml`에 추가
- [X] T003 [P] 모델 파일과 사용자별 실행 설정이 저장소에 포함되지 않도록 `.gitignore`에 `examples/yolo_vehicle/models/` 및 실제 `config.json`, `pipeline.json` 제외 규칙 추가

---

## 2단계: 기반 기능

**목적**: 모든 사용자 스토리를 차단하는 단계 간 산출물·설정·writable 프레임 계약 구현

**중요**: 이 단계가 완료되기 전에는 사용자 스토리 구현을 시작하지 않는다.

- [X] T004 [P] `FrameArtifacts`의 이름 유일성, 프레임 격리, 장치 검증, 단일 해제 및 닫힌 저장소 오류 계약 테스트를 `tests/contract/test_algorithm_artifacts.py`에 작성하고 실패 확인
- [X] T005 [P] 계약 1.0/1.1 플러그인 호출 호환성과 잘못된 함수 서명 거부 테스트를 `tests/contract/test_algorithm_contract.py`에 추가하고 실패 확인
- [X] T006 [P] 기반 GPU 프레임 핸들 등록 금지와 정상·오류·취소 시 산출물 정리 테스트를 `tests/failure/test_resource_cleanup.py`에 추가하고 실패 확인
- [X] T007 `GpuArtifact`, `FrameArtifacts` 및 산출물 계약 오류를 `src/videep/algorithms/artifacts.py`에 구현
- [X] T008 계약 버전 1.1의 `process(frame_view, artifacts)` 호출과 계약 1.0 하위 호환 검증을 `src/videep/algorithms/contracts.py` 및 `src/videep/algorithms/loader.py`에 구현
- [X] T009 `FrameView`가 기반 리소스 소유권을 노출하지 않으면서 현재 프레임의 산출물 저장소를 제공하도록 `src/videep/algorithms/view.py`를 확장
- [X] T010 프레임별 `FrameArtifacts` 생성, 세 단계 전달, 준비 토큰 대기 및 모든 종료 경로 정리를 `src/videep/core/pipeline.py`에 구현
- [X] T011 [P] 기존 문자열 참조와 참조별 옵션 객체를 모두 허용하는 하위 호환 설정 파싱 테스트를 `tests/unit/test_config.py`에 작성하고 실패 확인
- [X] T012 알고리즘 참조별 설정 옵션을 `AlgorithmContext.options`로 전달하도록 `src/videep/config.py`와 `src/videep/core/pipeline.py`를 확장
- [X] T013 [P] backend 고유 GPU 객체가 핵심 모듈 공개 형식으로 누출되지 않는지 `tests/contract/test_core_backend_independence.py`에 검사 추가
- [X] T014 [P] writable 여부가 명시된 프레임만 후처리에서 수정할 수 있고 출력 lease가 인코딩까지 유지되는 계약 테스트를 `tests/contract/test_frame_view.py`에 작성하고 실패 확인
- [X] T015 writable GPU 출력 프레임의 획득·완료 토큰·인코더 전달 계약을 `src/videep/backends/base.py`, `src/videep/core/frame.py`, `src/videep/core/pipeline.py`에 구현

**완료 기준**: 계약 1.0 플러그인이 그대로 통과하고 계약 1.1 플러그인이 프레임별 GPU 산출물을 안전하게 교환하며 모든 실패 경로에서 자원이 정리된다.

---

## 3단계: 사용자 스토리 1 - 차량 검출 결과 확인 (우선순위: P1) 🎯 MVP

**목표**: GPU 상주 프레임에서 자동차를 검출하고 각 자동차 주위에 경계 상자를 표시한다.

**독립 테스트**: 자동차가 있는 시험 입력에서는 기준 자동차가 상자로 표시되고, 자동차가 없는 입력은 원본 순서로 출력되며, 전체 프레임 CPU 왕복이 발생하지 않는지 확인한다.

### 사용자 스토리 1 테스트

- [X] T016 [P] [US1] 차량 설정의 필수 모델, 장치, 검출 임계값, 대상 종류 및 최대 차량 수 검증 테스트를 `tests/unit/test_vehicle_config.py`에 작성하고 실패 확인
- [X] T017 [P] [US1] `VehicleDetection` 좌표 제한, 신뢰도, 종류, 중복 제거 후 순서 테스트를 `tests/unit/test_vehicle_results.py`에 작성하고 실패 확인
- [X] T018 [P] [US1] 예제 전처리·추론·후처리 모듈의 역할, 계약 버전 및 산출물 이름 테스트를 `tests/contract/test_yolo_vehicle_contract.py`에 작성하고 실패 확인
- [X] T019 [US1] 자동차 있음·없음·일부 가림 입력의 경계 상자 출력과 프레임 순서 통합 테스트를 `tests/integration/test_yolo_vehicle_pipeline.py`에 작성하고 실패 확인

### 사용자 스토리 1 구현

- [X] T020 [P] [US1] 차량 예제 설정 데이터 클래스, 엄격한 JSON 파싱 및 단계별 오류를 `examples/yolo_vehicle/models.py`에 구현
- [X] T021 [P] [US1] `VehicleDetection`, 프레임 좌표 복원, 대상 종류 필터와 최대 결과 정규화를 `examples/yolo_vehicle/models.py`에 구현
- [X] T022 [P] [US1] DLPack 무복사 가져오기, CUDA 스트림 연결, NV12→RGB, 레터박스 및 정규화 연산을 `examples/yolo_vehicle/kernels.py`에 구현
- [X] T023 [US1] GPU 검출 입력과 좌표 복원 정보를 산출물로 게시하는 전처리 계약 1.1 플러그인을 `examples/yolo_vehicle/preprocess.py`에 구현
- [X] T024 [US1] YOLO 모델 단일 초기화·장치 검증·준비 실행과 GPU 텐서 검출 경로를 `examples/yolo_vehicle/inference.py`에 구현
- [X] T025 [US1] 대상 차량 필터링, GPU 중복 억제, 좌표 제한 및 `vehicle.analysis` 게시를 `examples/yolo_vehicle/inference.py`에 구현
- [X] T026 [US1] writable GPU 프레임에 차급 텍스트 없이 차량 경계 상자만 합성하는 커널을 `examples/yolo_vehicle/kernels.py` 및 `examples/yolo_vehicle/postprocess.py`에 구현
- [ ] T027 [US1] P1 실제 GPU 경로를 `tests/integration/test_yolo_vehicle_pipeline.py`에서 실행하고 검출 상자, 자동차 없음 처리, 프레임 순서 및 자원 해제를 통과시킴

**완료 기준**: 사용자 스토리 1만으로 차량 검출과 경계 상자 표시가 가능한 독립 MVP가 된다.

---

## 4단계: 사용자 스토리 2 - 자동차 크기 등급 표시 (우선순위: P2)

**목표**: 검출된 각 차량을 별도 모델로 소형·중형·대형 또는 미분류로 분류하고 상자에 텍스트와 신뢰도를 표시한다.

**독립 테스트**: 미리 만든 검출 결과를 입력하여 차급 정답과 표시 결과를 비교하며 사용자 스토리 1의 실제 YOLO 실행 없이도 분류·표시 기능을 검증한다.

### 사용자 스토리 2 테스트

- [X] T028 [P] [US2] 검출 ID별 1:1 분류 연결, 임계값 미만 미분류, 작은 ROI 및 다중 차량 정렬 테스트를 `tests/unit/test_vehicle_results.py`에 추가하고 실패 확인
- [X] T029 [P] [US2] 경계 상자·텍스트의 프레임 경계 제한, 레이블 색상 및 가장자리 배치 테스트를 `tests/unit/test_vehicle_postprocess.py`에 작성하고 실패 확인
- [X] T030 [US2] 가짜 검출 산출물을 사용한 ROI 일괄 분류와 소형·중형·대형·미분류 표시 통합 테스트를 `tests/integration/test_yolo_vehicle_pipeline.py`에 추가하고 실패 확인

### 사용자 스토리 2 구현

- [X] T031 [P] [US2] `VehicleClassification`, `VehicleAnalysisResult` 및 검출 ID 연결 검증을 `examples/yolo_vehicle/models.py`에 구현
- [X] T032 [P] [US2] 소형·중형·대형·미분류 및 신뢰도 숫자용 고정 bitmap glyph atlas를 `examples/yolo_vehicle/labels.py`에 정의
- [X] T033 [US2] GPU `roi_align` 차량 배치 생성, 차급 TorchScript 모델 단일 실행 및 임계값 적용을 `examples/yolo_vehicle/inference.py`에 구현
- [X] T034 [US2] glyph atlas 초기 GPU 업로드와 NV12 경계 상자·차급·신뢰도 합성 커널을 `examples/yolo_vehicle/kernels.py`에 구현
- [X] T035 [US2] 검출·분류 결과를 해당 상자와 정확히 연결하고 표시 완료 토큰을 게시하도록 `examples/yolo_vehicle/postprocess.py`를 완성
- [ ] T036 [US2] P2 실제 GPU 및 가짜 모델 경로를 `tests/integration/test_yolo_vehicle_pipeline.py`에서 실행해 다중 차량 차급 정확성, 미분류와 텍스트 표시를 통과시킴

**완료 기준**: 사용자 스토리 2는 가짜 검출 입력으로 독립 검증 가능하고, 사용자 스토리 1과 결합하면 전체 차량 분석 결과를 표시한다.

---

## 5단계: 사용자 스토리 3 - 예제를 복사하여 사용자 모델로 교체 (우선순위: P3)

**목표**: 사용자가 핵심 런타임 변경 없이 모델, 임계값, 대상 종류 및 표시 설정을 교체하고 잘못된 설정의 구체적인 오류를 확인한다.

**독립 테스트**: 호환되는 가짜 모델과 설정을 교체해 실행하고, 모델 누락·장치 불일치·잘못된 설정에서 첫 프레임 전에 예상 오류가 발생하는지 확인한다.

### 사용자 스토리 3 테스트

- [X] T037 [P] [US3] 모델 누락, 장치 불일치, 잘못된 레이블·임계값 및 알 수 없는 키 오류 메시지 계약을 `tests/contract/test_yolo_vehicle_contract.py`에 추가하고 실패 확인
- [X] T038 [P] [US3] 모델 경로와 검출·분류·표시 설정 교체가 핵심 파일 변경 없이 반영되는 테스트를 `tests/integration/test_yolo_vehicle_pipeline.py`에 추가하고 실패 확인

### 사용자 스토리 3 구현

- [X] T039 [P] [US3] 모든 지원 설정과 안전한 예시 값을 포함한 `examples/yolo_vehicle/config.example.json` 작성
- [X] T040 [P] [US3] 기존 RTSP 입력·출력과 차량 예제 플러그인 참조·옵션을 포함한 `examples/yolo_vehicle/pipeline.example.json` 작성
- [X] T041 [US3] 모델 파일 존재, CUDA 장치, YOLO 출력 및 차급 레이블을 첫 프레임 전에 검증하고 해결 지침이 포함된 단계별 오류를 `examples/yolo_vehicle/preprocess.py`, `examples/yolo_vehicle/inference.py`, `examples/yolo_vehicle/postprocess.py`에 구현
- [X] T042 [US3] 설치, 모델 준비, 설정 복사, 실행, 예상 화면, 설정 교체 및 문제 해결 절차를 한글로 `examples/yolo_vehicle/README.md`에 작성
- [X] T043 [US3] `specs/002-yolo-vehicle-plugin/quickstart.md`의 P3 교체·실패 시나리오를 실행하고 모든 계약 테스트를 통과시킴

**완료 기준**: 신규 사용자가 설명만으로 15분 이내에 예제를 설정하고 자신의 호환 모델로 교체할 수 있다.

---

## 6단계: 마무리 및 공통 품질

**목적**: 무복사 증거, 계측, 장시간 안정성 및 전체 문서 검증

- [X] T044 [P] 프레임별 차량 수, 미분류 수, 전처리·검출·분류·표시 GPU 지연과 오류 수를 `src/videep/telemetry/metrics.py` 및 예제 플러그인에 연결
- [X] T045 [P] 전체 프레임 `.cpu()`, `.numpy()`, 호스트 배열 변환 금지와 허용된 작은 메타데이터 전송량 검증을 `tests/performance/test_yolo_vehicle_zero_copy.py`에 구현
- [X] T046 GPU 이벤트 기반 단계별 p50/p95, 처리량, 장치 메모리와 GPU↔CPU 전송 측정을 `tests/performance/test_yolo_vehicle_zero_copy.py`에 구현
- [X] T047 30분 연속 실행의 프레임 순서, 메모리 증가, 산출물 누수 및 파이프라인 중단 검증을 `tests/performance/test_yolo_vehicle_zero_copy.py`에 구현
- [X] T048 [P] 모델 파일 및 선택적 GPU 의존성이 없을 때 핵심 패키지와 기존 플러그인 테스트가 정상 동작하는 회귀 검사를 `tests/contract/test_user_plugins.py`에 추가
- [X] T049 Ruff, mypy 및 전체 pytest를 실행하고 발견된 문제를 관련 `src/`, `examples/yolo_vehicle/`, `tests/` 파일에서 수정
- [ ] T050 `specs/002-yolo-vehicle-plugin/quickstart.md`의 설치·계약·실제 GPU·무복사·실패 경로를 순서대로 검증하고 실제 측정 결과를 `specs/002-yolo-vehicle-plugin/validation.md`에 기록

---

## 의존성 및 실행 순서

### 단계 의존성

- **1단계 준비**: 즉시 시작 가능
- **2단계 기반 기능**: 1단계 완료 후 진행하며 모든 사용자 스토리를 차단
- **3단계 사용자 스토리 1**: 기반 기능 완료 후 시작하는 권장 MVP
- **4단계 사용자 스토리 2**: 기반 기능 완료 후 가짜 검출 산출물로 독립 개발 가능하며 전체 통합은 사용자 스토리 1 완료 후 수행
- **5단계 사용자 스토리 3**: 기반 기능 완료 후 예시 설정·문서는 병렬 작성 가능하며 최종 검증은 사용자 스토리 1·2 완료 후 수행
- **6단계 마무리**: 제공하려는 모든 사용자 스토리 완료 후 수행

### 사용자 스토리 의존성 그래프

```text
준비 → 기반 기능 ─┬→ US1 차량 검출 MVP ─┐
                  ├→ US2 차급 분류 ──────┼→ 공통 품질 검증
                  └→ US3 설정·문서 ──────┘
```

- **US1**: 기반 기능 외 사용자 스토리 의존성 없음
- **US2**: 가짜 검출 결과로 독립 검증 가능, 실제 종단 간 검증만 US1 필요
- **US3**: 설정 및 오류 계약은 독립 검증 가능, 완성 예제 검증은 US1·US2 필요

### 스토리 내부 순서

- 테스트 작성 및 실패 확인 → 데이터 모델·설정 → GPU 연산 및 모델 실행 → 플러그인 연결 → 통합 검증
- GPU 출력은 준비 토큰 등록 후 다음 단계가 소비하며, 산출물 수명 테스트를 통과하기 전 최적화를 진행하지 않는다.

## 병렬 실행 예시

### 사용자 스토리 1

```text
T016 차량 설정 테스트
T017 차량 검출 결과 테스트
T018 예제 플러그인 계약 테스트
```

테스트 작성 후 `T020` 설정 모델과 `T022` GPU 전처리 커널은 서로 다른 파일에서 병렬 수행할 수 있다.

### 사용자 스토리 2

```text
T028 차급 결과 연결 테스트
T029 표시 경계 테스트
T032 GPU 글리프 atlas 정의
```

### 사용자 스토리 3

```text
T037 오류 메시지 계약 테스트
T038 설정 교체 통합 테스트
T039 예제 분석 설정
T040 예제 파이프라인 설정
```

## 구현 전략

### MVP 우선

1. 1단계 준비 완료
2. 2단계 기반 계약 완료
3. 3단계 사용자 스토리 1 완료
4. 차량 검출 상자와 무복사 경로를 독립 검증
5. 결과가 안정적일 때 차급 분류와 사용자 문서를 추가

### 점진적 제공

1. 기반 기능으로 계약 1.0 호환과 안전한 산출물 수명 확보
2. US1 차량 검출·상자 표시 MVP 제공
3. US2 차급 분류·텍스트 표시 추가
4. US3 모델 교체·설정·문서 제공
5. 장시간 및 무복사 측정 증거를 완료한 후 배포

## 참고

- `[P]` 작업은 파일 충돌과 선행 의존성이 없는 경우에만 병렬 수행한다.
- `[US1]`, `[US2]`, `[US3]`는 명세의 사용자 스토리 추적 표시이다.
- 실제 모델 파일은 저장소에 추가하지 않는다.
- GPU 내부 텐서 변환은 허용하지만 전체 프레임의 호스트 왕복은 금지한다.
- 각 완료 기준에서 독립 테스트를 실행한 뒤 다음 우선순위로 이동한다.
