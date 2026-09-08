# Videep

GPU 상주 단일 비디오 스트림 파이프라인을 제공하는 Python 프로젝트다. 코어는 백엔드 중립
`GpuFrame` 계약을 사용하며 첫 참조 백엔드는 NVIDIA GPU 비디오 코덱 경로다.

## 개발 설치

```powershell
uv sync --extra dev --extra nvidia
python -m pytest
```

사용자 전처리·추론·후처리는 신뢰된 동일 프로세스 Python 모듈이며 `module:object`로 지정한다.
정상 데이터 경로에는 전체 프레임 CPU 폴백이 없고, 지원되지 않는 무복사 조합은 시작 전에
실패한다. 현재 범위는 입력과 출력이 각각 하나인 단일 스트림이다.

## 사용자 알고리즘 플러그인

다음 파일의 최상위 `process(frame)` 함수를 각각 수정할 수 있다.

- `plugins/preprocess.py`: 전처리
- `plugins/inference.py`: 추론 및 모델 초기화
- `plugins/postprocess.py`: 후처리

각 파일은 서로 독립적으로 로드된다. 설정에서는 다음 참조를 사용한다.

```json
"algorithms": {
  "preprocess": "plugins.preprocess:Plugin",
  "inference": "plugins.inference:Plugin",
  "postprocess": "plugins.postprocess:Plugin"
}
```

`pipeline.example.json`을 복사하여 실행 설정으로 사용할 수 있다. 플러그인 변경 사항은 다음
파이프라인 시작부터 적용된다. `frame`은 호출 중에만 유효한 GPU 뷰이므로 저장하거나 CPU
배열로 변환하면 안 된다. GPU 라이브러리와 연결할 때는 `frame`의 DLPack 인터페이스를 사용한다.

## RTSP 입력과 Push 출력

입력과 출력 URI를 모두 `rtsp://`로 지정하면 입력에는 `DESCRIBE → SETUP → PLAY`, 출력에는
`ANNOUNCE → SETUP → RECORD` 절차를 사용한다. 별도 GStreamer나 FFmpeg 실행 파일은 필요하지
않으며 RTSP/RTP 전송은 Python 표준 라이브러리만 사용한다.

```json
{
  "input_uri": "rtsp://user:password@camera.example/live",
  "output_uri": "rtsp://publisher:password@server.example/channel",
  "backend": "nvidia",
  "device_id": "0",
  "algorithms": {
    "preprocess": "plugins.preprocess:Plugin",
    "inference": "plugins.inference:Plugin",
    "postprocess": "plugins.postprocess:Plugin"
  },
  "queue_capacity": 4
}
```

```powershell
videep start --config pipeline.json
```

실제 실행에는 프로젝트 루트의 `pipeline.json`에서 `input_uri`와 `output_uri`를 사용할 RTSP
주소로 변경한다. URL에 인증 정보가 필요하면 `rtsp://사용자:비밀번호@호스트:포트/경로`
형식을 사용한다.

현재 경량 RTSP 계층은 H.264, RTP interleaved TCP, 무인증 또는 Basic 인증을 지원한다.
UDP transport, Digest 인증, HEVC 및 RTSP-over-TLS는 아직 지원하지 않으며 협상 시 명시적인
오류를 반환한다. Basic 인증은 자격 증명을 암호화하지 않으므로 신뢰된 네트워크에서만
사용하거나 별도의 보안 터널을 적용해야 한다.

검증 절차는 [빠른 검증 가이드](specs/001-gpu-resident-pipeline/quickstart.md)와
[성능 검증 문서](docs/benchmarking.md)를 따른다.
