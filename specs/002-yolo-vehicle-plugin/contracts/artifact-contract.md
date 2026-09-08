# 단계 간 산출물 계약

## 버전과 호출

- 계약 `1.0`: `process(frame_view)`를 유지한다.
- 계약 `1.1`: `process(frame_view, artifacts)`를 사용한다.
- 로더는 호환되는 주 버전만 허용하며 1.0 플러그인은 변경 없이 동작한다.

## 공개 동작

```text
put_metadata(name, immutable_value)
get_metadata(name, expected_type=None)
put_gpu(name, artifact)
get_gpu(name, consumer_stage)
remove(name)
close()
```

## 불변 조건

1. 저장소는 단일 `frame_id`에 속한다.
2. 메타데이터는 좌표·레이블·신뢰도·식별자·측정값처럼 작은 값으로 제한한다.
3. 전체 호스트 프레임은 메타데이터로 등록할 수 없다.
4. GPU 산출물은 기반 `GpuFrame`의 lease나 네이티브 핸들을 소유하지 않는다.
5. 소비 단계는 준비 토큰을 기다린 뒤 접근한다.
6. 런타임은 산출물을 역등록 순서로 정확히 한 번 해제한다.
7. 플러그인은 호출 이후 `FrameView`를 보관하지 않는다.

## 차량 예제 이름

| 이름 | 생성 | 소비 | 종류 |
|---|---|---|---|
| `vehicle.detector_input` | 전처리 | 추론 | GPU |
| `vehicle.letterbox` | 전처리 | 추론 | 메타데이터 |
| `vehicle.analysis` | 추론 | 후처리 | 메타데이터 |
| `vehicle.overlay_ready` | 후처리 | 인코더 | 동기화 정보 |

중복 이름, 없는 이름, 장치 불일치, 닫힌 저장소 접근, 전체 CPU 프레임 등록과 이중 해제는 명시적 계약 오류로 처리한다.

