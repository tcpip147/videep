# 구현 계획: GPU 상주 단일 스트림 파이프라인

**브랜치**: `001-gpu-resident-pipeline` | **작성일**: 2026-09-08 | **명세**: [spec.md](spec.md)

**입력**: `/specs/001-gpu-resident-pipeline/spec.md`의 기능 명세

## 요약

하나의 비디오 스트림을 디코딩 → 전처리 → 추론 → 후처리 → 인코딩하는 동안 전체 프레임
픽셀을 GPU에 유지한다. 코어는 백엔드 중립 `GpuFrame`과 lease·동기화 계약, 제한된 프레임
큐 및 사용자 Python 알고리즘 계약을 제공한다. 첫 참조 백엔드는 NVIDIA GPU 비디오 코덱
경로로 구현하되 전용 형식은 어댑터 내부에 격리한다. 무복사와 성능은 계측 및 프로파일러
추적으로 검증한다.

## 기술 컨텍스트

**언어/버전**: Python 3.12

**주요 의존성**: 표준 `asyncio`, `typing`, `importlib`; DLPack Python protocol; NVIDIA
PyNvVideoCodec 참조 백엔드; pytest 및 pyperf 검증 도구

**저장소**: 운영 데이터 저장소 없음. 구성 파일과 벤치마크 JSON·프로파일러 산출물만 파일로 보존

**테스트**: pytest 단위·계약·통합·장애·장기 부하 테스트, pyperf 비교, 백엔드별 GPU 프로파일링

**대상 플랫폼**: 첫 참조 실행 환경은 NVIDIA GPU가 있는 64비트 Linux 또는 Windows;
코어 계약은 운영체제와 GPU 공급업체에 독립적

**프로젝트 유형**: Python 라이브러리와 CLI

**성능 목표**: 합의된 입력 프레임 속도의 99% 이상 처리, 동일 조건 5회 실행의 처리량과
p95 지연이 중앙값 대비 ±5%, 30분 연속 실행에서 누락·중복 0개

**제약**: 단일 입력·출력 스트림, 정상 경로 전체 프레임 GPU↔CPU 왕복 0회, 제한된 FIFO,
암묵적 프레임 삭제 금지, 제어/데이터 플레인 분리, 신뢰된 동일 프로세스 Python 모듈

**규모/범위**: 디코더·전처리·추론·후처리·인코더 5단계, 단계 간 큐 4개, 초기 NVIDIA
백엔드 1개, 전처리·추론·후처리 플러그인 역할 3개

## 헌법 준수 점검

*관문: Phase 0 이전과 Phase 1 설계 이후 모두 통과해야 한다.*

| 헌법 원칙 | 계획의 준수 근거 | 상태 |
|---|---|---|
| I. GPU 상주 데이터 경로 | 전체 프레임은 backend GPU 리소스 lease로만 이동하며 CPU 폴백을 금지한다. | 통과 |
| II. 백엔드 독립성 | 코어 Protocol은 불투명 리소스와 capability만 사용하고 NVIDIA 형식은 어댑터에 격리한다. | 통과 |
| III. 기본 데이터 모델로서의 GpuFrame | 모든 단계와 큐의 표준 프레임 형식이 `GpuFrame`이며 소유권·수명·형식·장치·동기화를 보존한다. | 통과 |
| IV. 데이터/제어 플레인 분리 | 제한된 전용 FIFO에는 frame lease만, 별도 이벤트 경로에는 명령·상태·메트릭만 흐른다. | 통과 |
| V. 측정 가능한 성능 | 전송·동기화·소유권·지연·처리량·메모리를 계측하고 재현 가능한 벤치마크와 추적을 남긴다. | 통과 |
| VI. 사용자 제공 알고리즘 | 세 알고리즘 역할을 독립 모듈로 로드하며 호출 범위 DLPack 뷰와 런타임 소유 lease를 사용한다. | 통과 |
| VII. 한글 명세 | 계획과 모든 Phase 0·1 산출물을 한글로 작성했다. | 통과 |
| VIII. Python 표준 언어 | 코어와 공개 인터페이스는 Python이며 네이티브 코덱은 Python 백엔드에서 호출한다. | 통과 |

Phase 1 재점검 결과, 데이터 모델은 lease와 동기화 책임을 명시하고 공개 계약은 CPU 폴백,
네이티브 형식 유출 및 제어 플레인 프레임 전달을 금지한다. 빠른 검증 가이드는 계약·종단 간·
무복사·30분 부하 검증을 포함한다. 정당화가 필요한 위반은 없다.

## 프로젝트 구조

### 이 기능의 문서

```text
specs/001-gpu-resident-pipeline/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── runtime-contract.md
│   └── telemetry-contract.md
└── tasks.md
```

`tasks.md`는 이 계획이 아니라 후속 `$speckit-tasks` 단계에서 생성한다.

### 소스 코드

```text
src/videep/
├── cli.py
├── config.py
├── core/
│   ├── capabilities.py
│   ├── frame.py
│   ├── lease.py
│   ├── pipeline.py
│   ├── queue.py
│   └── sync.py
├── backends/
│   ├── base.py
│   └── nvidia/
│       ├── backend.py
│       ├── decoder.py
│       ├── encoder.py
│       ├── interop.py
│       └── telemetry.py
├── algorithms/
│   ├── contracts.py
│   ├── loader.py
│   └── view.py
├── control/
│   ├── commands.py
│   └── events.py
└── telemetry/
    ├── metrics.py
    └── benchmark.py

tests/
├── unit/
├── contract/
│   ├── test_algorithm_contract.py
│   └── test_backend_contract.py
├── integration/
│   └── test_single_stream.py
├── failure/
│   ├── test_backpressure.py
│   └── test_resource_cleanup.py
└── performance/
    ├── test_zero_copy.py
    └── test_sustained_stream.py

artifacts/performance/
```

**구조 결정**: 단일 Python 패키지로 코어, 백엔드, 사용자 알고리즘, 제어 및 계측 경계를
분리한다. 백엔드 중립 모듈은 `core`에, 모든 공급업체 전용 의존성과 형식은
`backends/nvidia`에만 둔다. 테스트는 빠른 단위·계약 검증과 실제 GPU가 필요한 통합·성능
검증을 분리한다.

## 복잡성 추적

헌법 위반이나 별도 정당화가 필요한 복잡성은 없다.

## Phase 0: 조사 결과

[research.md](research.md)에 다음 결정을 확정했다.

- 백엔드 중립 GPU 리소스와 명시적 lease·동기화 계약
- NVIDIA 참조 백엔드와 시작 시 무복사 capability 협상
- `GpuFrame`을 표준 모델로 사용하고 Python에는 호출 범위 DLPack 뷰 제공
- `module:object` 사용자 알고리즘 로딩과 신뢰된 동일 프로세스 실행
- 기본 용량 4의 제한된 FIFO와 프레임 삭제 없는 역압
- 공통 계측과 백엔드 프로파일러를 결합한 성능·무복사 증거
- 압축 비트스트림과 GPU 상주 픽셀 프레임의 명시적 경계

미해결 `NEEDS CLARIFICATION` 항목은 없다.

## Phase 1: 설계 및 계약

- [data-model.md](data-model.md): `GpuFrame`, lease, 동기화, 실행, 단계, 알고리즘, 큐,
  capability 및 성능 기록의 필드·검증·상태 전이
- [runtime-contract.md](contracts/runtime-contract.md): 구성, 백엔드, 알고리즘, 제어·데이터
  플레인, 호환성과 오류 계약
- [telemetry-contract.md](contracts/telemetry-contract.md): 필수 메트릭, 벤치마크 결과와 회귀 판정
- [quickstart.md](quickstart.md): 계약, 종단 간, 무복사 및 30분 부하 검증 절차

설계 후 헌법 관문을 재검토했으며 모든 항목이 통과했다.
