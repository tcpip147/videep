# 데이터 모델: GPU 상주 단일 스트림 파이프라인

## GpuFrame

GPU에 상주하는 한 비디오 프레임의 표준 표현이다.

| 필드 | 의미 | 검증 규칙 |
|---|---|---|
| `frame_id` | 실행 내 고유 식별자 | 실행 내 중복 금지 |
| `sequence` | 입력 순서 | 0부터 단조 증가 |
| `pts` | 표시 타임스탬프 | 입력 시간 기준과 함께 존재 |
| `format` | 픽셀 형식과 색상 정보 | 협상된 형식 중 하나 |
| `dimensions` | 너비와 높이 | 모두 양수이며 backend 제한 충족 |
| `device_id` | 물리 GPU 식별 | 실행의 협상된 장치와 일치 |
| `planes` | plane별 크기, offset, pitch, modifier | 형식의 plane 수·배치와 일치 |
| `resource_lease` | 불투명 GPU 리소스 소유권 | 한 시점에 하나의 소유자 |
| `sync_token` | 생산 완료와 소비 완료 동기화 | wait/signal 순서가 유효 |
| `metadata` | 소량의 추론·추적 정보 | 전체 프레임 픽셀 포함 금지 |

`GpuFrame`은 생성 → 큐 대기 → 단계 소유 → 다음 단계로 이전을 반복한 뒤 pool 반환 또는
폐기 상태로 전이한다. lease 이전 후 이전 소유자는 접근할 수 없다.

## GpuResourceLease

기반 GPU 리소스의 독점 사용 권한과 수명을 나타낸다. `resource_id`, `backend_id`,
`device_id`, 접근 권한, 소유 단계, 세대 번호 및 반환 상태를 가진다. 복제는 금지하며
`transfer`, `borrow_view`, `release`만 허용한다. 빌린 뷰는 호출 범위를 벗어날 수 없다.

## SyncToken

생산자 완료와 소비자 시작 순서를 나타내는 백엔드 중립 동기화 정보이다. backend 식별자,
불투명 동기화 객체, timeline 값과 상태를 가진다. CPU 대기를 암묵적으로 수행하지 않으며
backend가 wait/signal을 계측한다.

## PipelineRun

단일 입력 스트림 실행을 나타낸다. 실행 식별자, 구성, 협상 결과, 상태, 프레임 카운트,
시작·종료 시각과 최종 오류를 가진다.

상태 전이는 다음과 같다.

```text
CREATED → VALIDATING → READY → RUNNING → DRAINING → COMPLETED
                  ↘ FAILED       ↘ STOPPING → STOPPED
```

`FAILED`, `STOPPED`, `COMPLETED`는 최종 상태이며 모든 lease가 회수되어야 진입할 수 있다.

## PipelineStage

디코딩, 전처리, 추론, 후처리 또는 인코딩 역할을 가진 처리 단계이다. 단계 식별자, 역할,
입출력 capability, 알고리즘 참조, 상태와 계측 식별자를 가진다. 처리 단계는 입력 lease를
소유한 동안만 프레임에 접근하고 출력 이전 또는 오류 시 반드시 소유권을 반환한다.

## AlgorithmComponent

외부 Python 모듈의 전처리·추론·후처리 구현이다. `module:object` 참조, 역할, 계약 버전,
지원 형식·장치, 초기화 상태와 오류 상태를 가진다. 세 역할은 서로 독립적으로 교체한다.

상태 전이는 `DISCOVERED → VALIDATED → INITIALIZED → ACTIVE → CLOSED`이며 어느 단계에서든
계약 또는 실행 오류가 발생하면 `FAILED`로 전이한다.

## FrameQueue

두 단계 사이의 제한된 FIFO이다. 큐 식별자, 상류·하류 단계, 최대 용량, 현재 깊이,
high-watermark, 누적 대기 시간과 상태를 가진다. 용량이 가득 차면 상류를 대기시키며
암묵적인 프레임 삭제는 허용하지 않는다.

## CapabilitySet

장치, 코덱, 픽셀 형식, 크기, plane 배치, 외부 핸들, 동기화 및 무복사 상호운용 기능의
집합이다. 모든 인접 단계의 교집합이 존재해야 실행이 `READY`가 된다.

## PerformanceRecord

한 검증 실행의 환경 지문, 입력 지문, 구성 지문, 준비 구간, 측정 구간, 프레임 수,
처리량, p50/p95/p99 지연, 단계별 GPU 시간, 큐 통계, peak GPU 메모리, GPU/CPU 전송
카운트와 프로파일러 증거 위치를 가진다. 기준 결과와 비교하려면 세 지문이 모두 일치해야 한다.
