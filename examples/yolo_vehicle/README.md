# YOLO 차량 분석 플러그인 예제

이 예제는 GPU 상주 영상에서 차량을 검출하고 별도 모델로 소형·중형·대형을 분류한 뒤 경계 상자와 레이블을 표시한다. 전체 프레임을 NumPy 또는 CPU 이미지로 변환하지 않는다.

## 준비

```powershell
uv sync --extra dev --extra nvidia --extra vehicle-example
Copy-Item examples\yolo_vehicle\config.example.json examples\yolo_vehicle\config.json
Copy-Item examples\yolo_vehicle\pipeline.example.json examples\yolo_vehicle\pipeline.json
```

다음 파일을 `examples/yolo_vehicle/models/`에 준비한다.

- `yolo-vehicle.pt`: Ultralytics에서 로드할 수 있고 `car`, `bus`, `truck` 이름을 출력하는 YOLO 모델

모델은 자동으로 다운로드하지 않는다. 사용 권한이 있는 모델을 직접 준비하고 `config.json`의 경로를 수정한다.

## 실행

`pipeline.json`의 입력 및 출력 RTSP 주소를 변경한 뒤 실행한다.

```powershell
.venv\Scripts\python.exe -m videep.cli start --config examples\yolo_vehicle\pipeline.json --stats-interval 5
```

## 수정 지점

- `preprocess.py`: 입력 크기와 색상·정규화 방식
- `inference.py`: YOLO 대상 종류, 차급 모델 및 결과 규칙
- `postprocess.py`: 표시 연결
- `kernels.py`: GPU 전처리와 경계 상자·텍스트 렌더링
- `labels.py`: 표시 레이블의 glyph atlas

설정에서는 검출·분류 신뢰도, IoU 기준, 최대 차량 수, 최소 ROI 크기와 색상을 바꿀 수 있다. 핵심 `src/videep` 파일을 변경할 필요가 없다.

## 오류 해결

- `[config] detector_model`: 모델 경로와 읽기 권한을 확인한다.
- `[detection] CUDA`: PyTorch CUDA 설치와 `device_id`를 확인한다.
- `[overlay] writable`: NVIDIA 디코더가 writable GPU 프레임을 제공하는지 확인한다.
- DLPack 오류: PyNvVideoCodec, CUDA 및 PyTorch가 같은 장치를 사용하는지 확인한다.

차량이 없거나 신뢰도가 낮은 프레임도 그대로 출력된다. 분류 신뢰도가 기준보다 낮거나 ROI가 너무 작으면 `미분류`로 표시한다.
