# 차량 분석 예제 설정 계약

UTF-8 JSON 객체를 사용하며 알 수 없는 키를 오류로 처리한다.

```json
{
  "detector_model": "models/yolo-vehicle.pt",
  "classifier_model": "models/vehicle-size-classifier.torchscript",
  "device_id": "0",
  "detection_confidence": 0.35,
  "classification_confidence": 0.60,
  "iou_threshold": 0.45,
  "max_vehicles": 32,
  "target_classes": ["car", "bus", "truck"],
  "min_crop_size": 16,
  "box_colors": {
    "소형": [0, 255, 0],
    "중형": [255, 200, 0],
    "대형": [255, 0, 0],
    "미분류": [160, 160, 160]
  }
}
```

초기화 시 문법·필수 키·범위, 모델 파일, 장치 일치, 모델 입출력·레이블, 최대 GPU 버퍼와 writable 출력 지원을 순서대로 검증한다. 오류에는 `config`, `preprocess`, `detection`, `classification`, `overlay` 단계와 실패 대상, 기대값, 실제값 및 수정 방향을 포함한다.

