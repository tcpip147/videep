# 작업: GPU 상주 단일 스트림 파이프라인

**입력**: `/specs/001-gpu-resident-pipeline/`의 설계 문서

**선행 문서**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**테스트**: 기능 명세와 헌법이 계약, 통합, 장애, 성능 및 무복사 검증을 요구하므로 테스트를
구현보다 먼저 작성한다.

**구성 방식**: 각 사용자 스토리를 독립적으로 구현하고 검증할 수 있도록 스토리별로 작업을
그룹화한다.

## 형식: `[ID] [P?] [스토리] 설명`

- **[P]**: 미완료 작업과 충돌하지 않는 별도 파일에서 병렬 수행 가능
- **[US1]~[US3]**: 기능 명세의 사용자 스토리 연결
- 모든 작업은 변경할 정확한 파일 경로를 포함한다.

## Phase 1: 설정

**목적**: Python 패키지, 개발 도구 및 계획된 디렉터리 구조 초기화

- [X] T001 `pyproject.toml`에 Python 3.12 패키지 메타데이터, pytest·pyperf 개발 의존성 및 `videep` CLI 진입점 정의
- [X] T002 [P] 계획의 모듈 경계에 맞춰 `src/videep/__init__.py`, `src/videep/core/__init__.py`, `src/videep/backends/__init__.py`, `src/videep/algorithms/__init__.py`, `src/videep/control/__init__.py`, `src/videep/telemetry/__init__.py` 생성
- [X] T003 [P] `pyproject.toml`에 Ruff 정적 검사·포맷과 mypy 엄격 타입 검사 설정 추가
- [X] T004 [P] `tests/conftest.py`에 GPU 필요 테스트 표식, 30분 실행 시간 옵션 및 테스트 아티팩트 경로 fixture 정의
- [X] T005 [P] `artifacts/performance/.gitkeep`와 `.gitignore`에 벤치마크·프로파일러 산출물 보존 규칙 정의

---

## Phase 2: 공통 기반

**목적**: 모든 사용자 스토리가 의존하는 백엔드 중립 데이터 모델과 런타임 기반 구현

**중요**: 이 단계가 완료될 때까지 사용자 스토리 구현을 시작할 수 없다.

- [X] T006 [P] `src/videep/core/capabilities.py`에 장치, 코덱, 픽셀 형식, plane 배치, 외부 핸들 및 동기화 capability 불변 모델 구현
- [X] T007 [P] `src/videep/core/sync.py`에 CPU 암묵 대기 없는 백엔드 중립 `SyncToken`과 wait/signal Protocol 구현
- [X] T008 [P] `src/videep/core/lease.py`에 단일 소유자 이전, 호출 범위 borrow 및 중복 해제를 차단하는 `GpuResourceLease` 구현
- [X] T009 `src/videep/core/frame.py`에 T006~T008을 조합하여 형식·장치·plane·소유권·수명·동기화를 보존하는 `GpuFrame` 구현
- [X] T010 [P] `src/videep/core/queue.py`에 제한된 FIFO, 기본 용량 4, 생산자 대기, EOS/ERROR 신호 및 암묵적 삭제 금지 구현
- [X] T011 [P] `src/videep/backends/base.py`에 네이티브 형식을 노출하지 않는 장치·decoder·encoder·pool·동기화·계측 Protocol 정의
- [X] T012 [P] `src/videep/config.py`에 단일 입력·출력, 단계별 큐 용량, 알고리즘 참조, 오류·종료 정책 및 측정 설정 검증 구현
- [X] T013 [P] `src/videep/control/commands.py`와 `src/videep/control/events.py`에 픽셀·GPU 핸들을 금지하는 start/stop/status 명령 및 상태 이벤트 모델 구현
- [X] T014 [P] `tests/unit/test_capabilities.py`에 capability 교집합, 장치 불일치 및 무복사 협상 실패 테스트 작성
- [X] T015 [P] `tests/unit/test_frame_lease.py`에 frame 불변식, lease 이전·만료·중복 해제 및 sync 순서 테스트 작성
- [X] T016 [P] `tests/failure/test_backpressure.py`에 제한 용량, FIFO 순서, 생산자 대기, EOS/ERROR 및 프레임 무삭제 테스트 작성
- [X] T017 `src/videep/core/pipeline.py`에 실행 상태 전이, capability 사전 협상, 단계 수명 주기, 종료 시 lease 회수 골격 구현

**체크포인트**: 백엔드 중립 프레임·소유권·동기화·큐·실행 계약이 단위 테스트로 검증된다.

---

## Phase 3: 사용자 스토리 1 - 단일 비디오 스트림 처리 (P1) 🎯 MVP

**목표**: 단일 입력을 디코딩부터 인코딩까지 순서대로 GPU에 상주시켜 출력하고 안전하게 종료

**독립 테스트**: 알려진 입력을 처리해 출력 수와 순서를 대조하고 전체 프레임 GPU → CPU →
GPU 왕복 0회와 모든 GPU lease 회수를 확인한다.

### 사용자 스토리 1 테스트

- [X] T018 [P] [US1] `tests/contract/test_backend_contract.py`에 모든 backend가 충족할 capability, pool, decoder/encoder, sync 및 전송 계측 계약 테스트 작성
- [X] T019 [P] [US1] `tests/integration/test_single_stream.py`에 정상 시작, 5단계 순서 처리, 프레임 순서·개수 보존, EOS drain 및 완료 상태 테스트 작성
- [X] T020 [P] [US1] `tests/failure/test_resource_cleanup.py`에 중지, 디코딩 실패, GPU 할당 실패 및 동시 EOS에서 모든 lease 회수 테스트 작성
- [X] T021 [P] [US1] `tests/performance/test_zero_copy.py`에 정상 경로 전체 프레임 GPU/CPU 왕복 0회와 프로파일러 증거 존재 검증 작성

### 사용자 스토리 1 구현

- [X] T022 [P] [US1] `src/videep/backends/nvidia/backend.py`에 장치 탐색, capability 보고 및 백엔드 구성 팩터리 구현
- [X] T023 [P] [US1] `src/videep/backends/nvidia/interop.py`에 GPU 리소스 pool, 불투명 lease, 장치 일치, DLPack 준비 및 동기화 어댑터 구현
- [X] T024 [P] [US1] `src/videep/backends/nvidia/decoder.py`에 압축 입력을 GPU 상주 `GpuFrame`으로 디코딩하고 EOS/오류를 전파하는 어댑터 구현
- [X] T025 [P] [US1] `src/videep/backends/nvidia/encoder.py`에 GPU 상주 `GpuFrame` 입력, 압축 출력 및 리소스 반환 어댑터 구현
- [X] T026 [US1] `src/videep/core/pipeline.py`에 decoder→preprocess→inference→postprocess→encoder 실행 루프, 큐 소유권 이전, 역압, drain 및 실패 정리 구현
- [X] T027 [US1] `src/videep/cli.py`에 구성 로드, 단일 스트림 start/stop/status 실행과 최종 상태 출력 구현
- [X] T028 [US1] `tests/integration/test_single_stream.py`의 고정 입력 검증을 실행 가능하게 하는 passthrough 전처리·추론·후처리 fixture를 `tests/fixtures/passthrough_algorithms.py`에 구현

**체크포인트**: 사용자 스토리 1만으로 GPU 상주 단일 스트림 MVP를 실행하고 독립 검증할 수 있다.

---

## Phase 4: 사용자 스토리 2 - 독립적인 알고리즘 구성 (P2)

**목표**: 외부 Python 전처리·추론·후처리를 코어 변경 없이 각각 교체하고 GPU 리소스 계약 유지

**독립 테스트**: 각 역할을 한 번에 하나씩 대체하여 나머지 단계와 코어 변경 없이 처리하고,
만료된 뷰와 전체 프레임 CPU 전송 요구를 거부하는지 확인한다.

### 사용자 스토리 2 테스트

- [X] T029 [P] [US2] `tests/contract/test_algorithm_contract.py`에 `module:object` 로딩, 역할별 Protocol, 계약 버전, 호출 수명 및 예외 변환 테스트 작성
- [X] T030 [P] [US2] `tests/contract/test_frame_view.py`에 DLPack `copy=False`, 소비자 스트림 전달, 만료 후 접근 및 리소스 소유권 획득 금지 테스트 작성
- [X] T031 [P] [US2] `tests/integration/test_algorithm_replacement.py`에 전처리·추론·후처리의 개별 교체와 GPU 상주 경로 보존 테스트 작성

### 사용자 스토리 2 구현

- [X] T032 [P] [US2] `src/videep/algorithms/contracts.py`에 역할별 구조적 Protocol, 계약 버전과 validate/initialize/process/close 수명 주기 정의
- [X] T033 [P] [US2] `src/videep/algorithms/loader.py`에 `module:object` import, 시작 시 서명·역할·버전 검증 및 명확한 오류 보고 구현
- [X] T034 [P] [US2] `src/videep/algorithms/view.py`에 호출 범위 `FrameView`, DLPack 장치 질의, 복사 금지와 소비자 스트림 동기화 구현
- [X] T035 [US2] `src/videep/core/pipeline.py`에 역할별 사용자 구성요소 초기화·독립 교체·호출·예외 격리·close 및 lease 회수 연결
- [X] T036 [US2] `src/videep/config.py`에 전처리·추론·후처리별 외부 모듈 참조와 capability 계약 사전 검증 연결

**체크포인트**: 세 알고리즘 역할을 독립적으로 교체하며 런타임이 GPU 리소스 소유권을 유지한다.

---

## Phase 5: 사용자 스토리 3 - 부하와 성능 상태 관찰 (P3)

**목표**: 처리량, 지연, 메모리, 전송, 동기화, 소유권과 역압을 관찰하고 성능 회귀를 재현

**독립 테스트**: 고정 입력과 환경에서 결과를 5회 수집해 비교하고 30분 부하에서 큐 상한,
메모리 안정성, 처리율 및 전체 프레임 전송 0회를 검증한다.

### 사용자 스토리 3 테스트

- [X] T037 [P] [US3] `tests/unit/test_metrics.py`에 필수 메트릭, 픽셀·네이티브 핸들 유출 금지 및 percentile 집계 테스트 작성
- [X] T038 [P] [US3] `tests/performance/test_sustained_stream.py`에 30분 처리율 99%, 큐 상한, 프레임 보존 및 GPU 메모리 안정성 검증 작성
- [X] T039 [P] [US3] `tests/performance/test_reproducibility.py`에 동일 지문 5회 처리량·p95 ±5% 비교와 지문 불일치 거부 테스트 작성

### 사용자 스토리 3 구현

- [X] T040 [P] [US3] `src/videep/telemetry/metrics.py`에 단계·큐·pool·전송·동기화·지연·처리량 메트릭과 안전한 라벨 구현
- [X] T041 [P] [US3] `src/videep/backends/nvidia/telemetry.py`에 GPU 이벤트 시간, 메모리 사용량, 방향별 전체 프레임 전송 및 프로파일러 상관관계 구현
- [X] T042 [P] [US3] `src/videep/telemetry/benchmark.py`에 입력·구성·환경 지문, 준비 구간, 원시 JSON, p50/p95/p99 및 기준 비교 구현
- [X] T043 [US3] `src/videep/core/pipeline.py`에 단계·큐·lease 수명과 실행 상태 계측 지점을 연결
- [X] T044 [US3] `src/videep/control/events.py`와 `src/videep/cli.py`에 데이터 플레인 정체와 독립적인 상태·오류·메트릭 조회 구현

**체크포인트**: 성능 및 무복사 주장이 공통 측정값과 백엔드 프로파일러 증거로 재현된다.

---

## Phase 6: 마무리 및 교차 관심사

**목적**: 전체 스토리의 품질 관문, 문서와 운영 검증 완성

- [X] T045 [P] `tests/contract/test_core_backend_independence.py`에 `src/videep/core/`의 NVIDIA·CUDA·Vulkan·VA-API·Direct3D·Metal 구체 형식 import 금지 검사 작성
- [X] T046 [P] `README.md`에 설치, 신뢰된 플러그인 모델, 단일 스트림 실행, 지원 범위와 CPU 전체 프레임 폴백 금지 문서화
- [X] T047 [P] `docs/benchmarking.md`에 동일 환경 재현, 기준 생성, 프로파일러 증거 수집 및 회귀 판정 절차 문서화
- [ ] T048 `specs/001-gpu-resident-pipeline/quickstart.md`의 계약·통합·무복사·30분 부하 명령을 실행하고 결과를 `artifacts/performance/validation-summary.md`에 기록
- [X] T049 `pyproject.toml`의 Ruff, mypy 및 pytest 전체 품질 관문을 실행하고 발견된 결함을 해당 `src/videep/` 또는 `tests/` 파일에서 수정

---

## 의존성 및 실행 순서

### 단계 의존성

- **Phase 1 설정**: 즉시 시작할 수 있다.
- **Phase 2 공통 기반**: Phase 1 완료 후 진행하며 모든 사용자 스토리를 차단한다.
- **Phase 3 US1**: Phase 2 이후 시작하며 단일 스트림 MVP를 제공한다.
- **Phase 4 US2**: Phase 2 이후 독립 착수할 수 있으나 실제 NVIDIA 종단 간 검증은 US1의
  T022~T026 완료 후 수행한다.
- **Phase 5 US3**: Phase 2 이후 공통 계측 구현을 착수할 수 있으나 장기 성능 검증은 US1의
  실행 경로 완료 후 수행한다.
- **Phase 6 마무리**: 제공하려는 모든 사용자 스토리 완료 후 수행한다.

### 사용자 스토리 의존성

```text
설정 → 공통 기반 → US1(MVP)
                 ├→ US2 알고리즘 교체
                 └→ US3 관측·성능
US1 + US2 + US3 → 마무리
```

- **US1 (P1)**: 공통 기반에만 의존하며 독립적인 MVP이다.
- **US2 (P2)**: 계약과 모듈 로더는 독립 구현 가능하다. 종단 간 인수 검증만 US1 실행 경로를 사용한다.
- **US3 (P3)**: 메트릭과 벤치마크 기록은 독립 구현 가능하다. 부하 검증만 US1 실행 경로를 사용한다.

### 스토리 내부 순서

- 각 테스트 작업을 먼저 작성하고 예상 이유로 실패함을 확인한다.
- 모델과 계약 → 백엔드·서비스 → 파이프라인 연결 → 종단 간 검증 순으로 진행한다.
- story 체크포인트를 통과한 뒤 다음 우선순위로 이동한다.

### 병렬 실행 기회

- Phase 1의 T002~T005는 T001과 파일 충돌이 없는 범위에서 병렬 수행한다.
- Phase 2의 capability, sync, lease, queue, backend, config, control 모델과 각 테스트를 병렬 작성한다.
- US1의 네 테스트와 NVIDIA backend 구성요소 네 개를 각각 병렬 작성한 뒤 파이프라인에 통합한다.
- US2의 계약·뷰·통합 테스트와 contracts·loader·view 구현을 병렬 작성한다.
- US3의 테스트 세 개와 metrics·backend telemetry·benchmark 구현을 병렬 작성한다.
- 공통 기반 완료 후 US2와 US3의 독립 모듈을 US1 실행 경로와 병렬 개발할 수 있다.

## 병렬 실행 예시: 사용자 스토리 1

```text
T018: tests/contract/test_backend_contract.py의 백엔드 계약 테스트
T019: tests/integration/test_single_stream.py의 종단 간 테스트
T020: tests/failure/test_resource_cleanup.py의 실패 정리 테스트
T021: tests/performance/test_zero_copy.py의 무복사 테스트

T022: src/videep/backends/nvidia/backend.py의 백엔드 팩터리
T023: src/videep/backends/nvidia/interop.py의 GPU 리소스 상호운용
T024: src/videep/backends/nvidia/decoder.py의 디코더
T025: src/videep/backends/nvidia/encoder.py의 인코더
```

## 병렬 실행 예시: 사용자 스토리 2

```text
T029: tests/contract/test_algorithm_contract.py의 알고리즘 계약 테스트
T030: tests/contract/test_frame_view.py의 DLPack 뷰 테스트
T031: tests/integration/test_algorithm_replacement.py의 단계 교체 테스트

T032: src/videep/algorithms/contracts.py의 역할별 Protocol
T033: src/videep/algorithms/loader.py의 모듈 로더
T034: src/videep/algorithms/view.py의 호출 범위 FrameView
```

## 병렬 실행 예시: 사용자 스토리 3

```text
T037: tests/unit/test_metrics.py의 메트릭 테스트
T038: tests/performance/test_sustained_stream.py의 30분 부하 테스트
T039: tests/performance/test_reproducibility.py의 재현성 테스트

T040: src/videep/telemetry/metrics.py의 공통 메트릭
T041: src/videep/backends/nvidia/telemetry.py의 GPU 계측
T042: src/videep/telemetry/benchmark.py의 결과 기록과 비교
```

## 구현 전략

### MVP 우선

1. Phase 1 설정을 완료한다.
2. Phase 2 공통 기반을 완료하고 단위·장애 테스트를 통과한다.
3. Phase 3 사용자 스토리 1을 완료한다.
4. 단일 스트림의 프레임 순서, GPU 상주, EOS 및 리소스 회수를 독립 검증한다.
5. MVP 결과를 고정한 뒤 알고리즘 확장과 성능 관측을 추가한다.

### 점진적 제공

1. 설정 + 공통 기반 → 백엔드 중립 계약 준비
2. US1 → GPU 상주 단일 스트림 MVP
3. US2 → 사용자 알고리즘의 독립 교체
4. US3 → 관측 가능한 성능과 회귀 증거
5. 마무리 → 전체 품질 관문과 운영 문서

### 병렬 팀 전략

공통 기반 이후 한 작업자는 US1 백엔드와 실행 경로를, 다른 작업자는 US2 알고리즘 계약을,
세 번째 작업자는 US3 계측과 벤치마크를 진행한다. 실제 GPU 종단 간 검증은 US1 실행 경로가
준비된 뒤 합류한다.

## 참고

- `[P]` 작업은 서로 다른 파일을 대상으로 하며 선행 작업의 미완료 결과를 요구하지 않는다.
- `[USn]`은 기능 명세 사용자 스토리 추적용이다.
- 테스트는 구현 전에 실패하는 상태를 확인한 뒤 구현으로 통과시킨다.
- 네이티브 GPU 형식은 `src/videep/backends/nvidia/` 밖으로 노출하지 않는다.
- 전체 프레임 CPU 접근 또는 폴백이 필요하면 구현하지 말고 별도 명세와 헌법 승인을 요청한다.
