# 빠른 검증 가이드

## 사전 조건

- Python 3.12 개발 환경
- 지원되는 NVIDIA GPU, 드라이버와 Video Codec SDK 호환 런타임
- 디코딩과 인코딩이 모두 지원되는 고정 테스트 비디오
- 계약을 충족하는 전처리·추론·후처리 테스트 모듈
- GPU 메모리 전송을 추적할 수 있는 NVIDIA 프로파일러

구체 계약은 [런타임 계약](contracts/runtime-contract.md), 측정값은
[성능 및 관측 계약](contracts/telemetry-contract.md), 리소스 상태는
[데이터 모델](data-model.md)을 따른다.

## 1. 개발 환경 검증

```powershell
python --version
python -m pytest --collect-only
```

Python 3.12가 선택되고 단위·계약·통합·성능 검증 항목이 오류 없이 수집되어야 한다.

## 2. 백엔드 및 알고리즘 계약 검증

```powershell
python -m pytest tests/contract -v
```

다음 결과를 확인한다.

- 코어 계약에 NVIDIA 또는 그래픽 API 네이티브 형식이 노출되지 않는다.
- 장치·형식·메모리·동기화 capability 불일치가 시작 전에 거부된다.
- 전처리·추론·후처리 모듈을 각각 독립적으로 교체할 수 있다.
- lease 이전, 만료된 뷰 접근과 오류 시 리소스 회수가 검증된다.

## 3. 단일 스트림 종단 간 검증

```powershell
python -m pytest tests/integration/test_single_stream.py -v
```

고정 입력의 프레임 수와 순서가 출력과 일치하고, 단계별 큐가 제한된 용량을 지키며,
EOS 이후 모든 프레임과 GPU 리소스가 정리되어야 한다.

## 4. 무복사 증거 수집

```powershell
python -m pytest tests/performance/test_zero_copy.py -v
```

동일 실행을 프로파일러로 추적한다. 공통 계측의 전체 프레임 GPU/CPU 왕복 횟수가 0이고,
프로파일러에서도 해당 방향의 전체 프레임 복사가 없어야 한다. API 표면만으로 통과 판정하지
않는다.

## 5. 30분 부하 및 회귀 검증

```powershell
python -m pytest tests/performance/test_sustained_stream.py -v --duration=1800
python -m pyperf compare_to artifacts/performance/baseline.json artifacts/performance/candidate.json
```

큐 용량 초과와 프레임 누락·중복이 없고, 준비 구간 이후 GPU 메모리가 지속 증가하지 않으며,
처리량이 입력 속도의 99% 이상이어야 한다. 동일 조건 5회 결과의 처리량과 p95 지연 시간은
중앙값 대비 ±5% 범위여야 한다.
