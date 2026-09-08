# 데이터 모델: 차량 분석 플러그인 예제

## `FrameArtifacts`

한 `GpuFrame`이 세 플러그인 단계를 지나는 동안 런타임이 소유하는 산출물 모음이다.

| 필드 | 형식 | 설명 |
|---|---|---|
| `frame_id` | 문자열 | 원본 프레임 식별자 |
| `metadata` | 이름→불변 값 | 좌표·레이블·신뢰도·측정값 |
| `gpu_artifacts` | 이름→`GpuArtifact` | 플러그인 할당 GPU 버퍼 |
| `closed` | 불리언 | 정리 완료 여부 |

규칙: 이름은 프레임 내에서 유일하고, 다른 프레임과 재사용하지 않으며, 닫힌 저장소에 접근할 수 없다. 기반 프레임 리소스와 lease를 등록할 수 없고 모든 산출물은 정상·오류·취소에서 정확히 한 번 정리한다.

```text
생성 → 전처리 기록 → 추론 기록 → 후처리 소비 → 정리
  └──────────── 오류 또는 취소 ───────────→ 정리
```

## `GpuArtifact`

| 필드 | 형식 | 설명 |
|---|---|---|
| `value` | 불투명 객체 | 핵심이 해석하지 않는 GPU 텐서 |
| `backend_id`, `device_id` | 문자열 | 생성 백엔드와 장치 |
| `producer_stage` | 단계 | 생성 단계 |
| `ready_token` | 선택적 토큰 | 소비 전 동기화 |
| `release` | 콜백 | 단일 호출 자원 정리 |

## `VehicleDetection`

| 필드 | 형식 | 규칙 |
|---|---|---|
| `detection_id` | 정수 | 프레임 내 유일 |
| `x1`, `y1`, `x2`, `y2` | 실수 | 프레임 범위, 양의 영역 |
| `object_class` | 문자열 | 설정된 차량 종류 |
| `confidence` | 실수 | 0~1, 기준 이상 |

## `VehicleClassification`

| 필드 | 형식 | 규칙 |
|---|---|---|
| `detection_id` | 정수 | 검출 결과와 1:1 연결 |
| `size_class` | 열거형 | 소형·중형·대형·미분류 |
| `confidence` | 실수 | 0~1, 기준 미만은 미분류 |

## `VehicleAnalysisResult`

프레임 식별자, 안정적인 순서의 검출 목록, 1:1 차급 목록과 단계별 처리 시간을 가진다.

## `VehiclePluginConfig`

| 필드 | 기본값 | 규칙 |
|---|---|---|
| `detector_model` | 필수 | 존재하고 읽을 수 있음 |
| `classifier_model` | 필수 | 존재하고 읽을 수 있음 |
| `device_id` | 파이프라인 장치 | 파이프라인과 일치 |
| `detection_confidence` | `0.35` | 0~1 |
| `classification_confidence` | `0.60` | 0~1 |
| `iou_threshold` | `0.45` | 0~1 |
| `max_vehicles` | `32` | 1 이상 |
| `target_classes` | `car,bus,truck` | 지원 종류의 비어 있지 않은 부분집합 |
| `min_crop_size` | `16` | 1 이상 |
| `box_colors` | 등급별 기본색 | RGB 각 0~255 |

## 관계

```text
GpuFrame 1 ── 1 FrameArtifacts ── 0..N GpuArtifact
GpuFrame 1 ── 1 VehicleAnalysisResult
VehicleAnalysisResult 1 ── 0..N VehicleDetection
VehicleDetection 1 ── 1 VehicleClassification
VehiclePluginConfig 1 ── 1 예제 플러그인 세트
```

