# 기술 조사: GPU 상주 단일 스트림 파이프라인

## 결정 1: 백엔드 중립 GPU 리소스 계약

**결정**: 코어는 `GpuFrame`, `GpuResourceLease`, `GpuDevice`, `SyncToken`과 디코더·인코더
백엔드 계약만 사용한다. 네이티브 리소스는 불투명 핸들로 백엔드가 보유한다. 시작 시 장치,
핸들 종류, 픽셀 형식, plane 배치, 메모리 modifier 및 동기화 기능을 협상하며 모든 조건이
호환될 때만 무복사 경로로 인정한다.

**근거**: 외부 GPU 메모리 상호운용은 동일 장치 식별, 호환 가능한 메모리 배치와 명시적
동기화가 필요하다. 이 정보를 코어의 백엔드 중립 계약으로 보존하면 공급업체 형식 유출 없이
소유권과 동기화를 검증할 수 있다.

**검토한 대안**: Vulkan을 코어 표준 형식으로 삼는 방안은 다른 API를 Vulkan 의미론에
종속시키므로 제외했다. FFmpeg 하드웨어 프레임을 표준 모델로 삼는 방안은 해당 라이브러리와
백엔드별 형식이 코어에 노출되므로 어댑터 내부 사용으로 제한한다.

**참고**: [Vulkan Video](https://docs.vulkan.org/spec/latest/chapters/videocoding.html),
[CUDA 그래픽 상호운용](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/graphics-interop.html),
[libva DRM PRIME](https://github.com/intel/libva/blob/master/va/va_drmcommon.h)

## 결정 2: NVIDIA 참조 백엔드

**결정**: 첫 참조 백엔드는 NVIDIA의 GPU 메모리 디코딩·인코딩 기능을 사용한다. 이 선택은
백엔드 구현에만 한정하며 코어와 사용자 알고리즘 계약은 NVIDIA 형식을 가져오지 않는다.
호환되는 무복사 경로를 구성할 수 없으면 시작 단계에서 실패시킨다.

**근거**: 단일 스트림의 디코딩부터 인코딩까지 GPU 상주를 직접 검증할 수 있는 공식 Python
경로와 프로파일링 도구가 제공된다. 하나의 완성된 참조 구현으로 계약의 실현 가능성을 먼저
입증하면서 후속 백엔드가 같은 계약 시험을 재사용할 수 있다.

**검토한 대안**: 최초 릴리스에서 여러 백엔드를 동시에 구현하면 계약 안정화 전 범위가
과도하게 커진다. CPU 기반 코덱 폴백은 정상 데이터 경로의 헌법 제약을 위반하므로 제외했다.

**참고**: [PyNvVideoCodec 프로그래밍 가이드](https://docs.nvidia.com/video-technologies/pynvvideocodec/pynvc-api-prog-guide/using_pynvvideocodec_apis.html),
[NVIDIA Video Codec SDK](https://docs.nvidia.com/video-technologies/video-codec-sdk/13.1/index.html)

## 결정 3: `GpuFrame`과 DLPack 뷰

**결정**: `GpuFrame`은 GPU 리소스의 형식, plane, 장치, 소유권, 수명과 동기화를 보존하는
표준 모델이다. Python 알고리즘에는 호출 범위의 `FrameView`만 제공한다. 조밀하거나 stride로
표현 가능한 계산용 plane은 DLPack으로 노출하고 소비자는 `copy=False`와 현재 실행 스트림을
전달해야 한다. 다중 plane이나 불투명 텍스처 정보는 백엔드 중립 프레임 계약에 남긴다.

**근거**: DLPack은 장치 중립 배열 교환, 복사 금지, 스트림 동기화와 소유권 이전 규칙을
정의하지만 비디오 표면 전체의 modifier와 외부 fence를 모두 표현하지는 않는다.

**검토한 대안**: NumPy와 호스트 버퍼는 GPU 상주 원칙을 위반한다. CUDA Array Interface는
공급업체 종속이므로 공개 계약에서 제외한다. DLPack 자체를 `GpuFrame`으로 사용하는 방안은
다중 plane 비디오 리소스 표현이 불충분하여 제외했다.

**참고**: [DLPack Python 사양](https://dmlc.github.io/dlpack/latest/python_spec.html)

## 결정 4: Python 플러그인 계약과 신뢰 모델

**결정**: 전처리·추론·후처리 구성요소는 `module:object` 참조로 로드하고 구조적 Protocol 및
시작 시 계약 검증을 적용한다. v1은 신뢰된 모듈을 동일 프로세스에서 실행하며, 프레임별
런타임 타입 검사는 하지 않는다. 예외 변환, 중단, 동기화 및 lease 회수는 런타임이 담당한다.

**근거**: 명시적 모듈 참조는 재현 가능하며 구조적 계약은 외부 모듈에 특정 상속을 강제하지
않는다. GPU IPC가 필요한 프로세스 격리를 피하면 리소스 수명과 동기화 계약을 단순화한다.

**검토한 대안**: 파일 경로 직접 로딩은 패키지 상대 import와 배포 재현성이 약하다. entry
point 전용 발견은 개발 모듈 사용이 번거롭다. 별도 프로세스 격리는 GPU IPC와 보안 모델이
필요하므로 후속 기능으로 남긴다.

**참고**: [Python importlib](https://docs.python.org/3/library/importlib.html#importlib.import_module),
[Python Protocol](https://docs.python.org/3/library/typing.html#typing.Protocol),
[PyPA entry points](https://packaging.python.org/en/latest/specifications/entry-points/)

## 결정 5: 제한된 데이터 플레인과 역압

**결정**: 각 단계 사이는 기본 용량 4의 제한된 FIFO로 연결하며 항목은 프레임 lease,
타임스탬프와 동기화 토큰이다. 큐가 가득 차면 상류 생산자를 대기시키고 프레임은 기본적으로
버리지 않는다. EOS와 오류는 명시적인 데이터 플레인 신호로 전파하며 제어 명령과 메트릭은
별도의 제어 플레인을 사용한다.

**근거**: 제한된 큐는 GPU 메모리 사용량을 상한 내에 두고 순서와 역압을 명확하게 만든다.

**검토한 대안**: 무제한 큐는 정체 시 GPU 메모리가 계속 증가한다. 최신 프레임만 유지하거나
암묵적으로 버리는 정책은 프레임 보존 요구를 위반하므로 v1에서 제외한다.

**참고**: [Python asyncio Queue](https://docs.python.org/3/library/asyncio-queue.html)

## 결정 6: 성능 및 무복사 증거

**결정**: 상시 계측은 단계별 처리량과 지연, 큐 깊이·대기, pool 사용량, 메모리와 전송
카운터를 기록한다. GPU 시간은 백엔드 장치 이벤트로 측정한다. 장시간 벤치마크는 준비 구간
후 원시 결과와 환경 정보를 저장하며, 공통 전송 카운터와 백엔드별 프로파일러 추적을 모두
사용해 전체 프레임 GPU↔CPU 전송 0회를 입증한다.

**근거**: CPU 벽시계만으로 비동기 GPU 완료 시점이나 숨은 전송을 증명할 수 없다. 재현 가능한
환경 정보와 원시 측정값이 있어야 회귀를 비교할 수 있다.

**검토한 대안**: API에 복사 호출이 없다는 사실만으로 무복사를 선언하는 방식과 Python
타이머만 사용하는 방식은 제외했다.

**참고**: [pytest](https://docs.pytest.org/en/stable/how-to/index.html),
[pyperf](https://pyperf.readthedocs.io/en/stable/),
[Nsight Systems](https://docs.nvidia.com/nsight-systems/UserGuide/index.html)

## 결정 7: 압축 비트스트림 경계

**결정**: GPU 상주 의무는 전체 비디오 프레임 픽셀 데이터에 적용한다. 압축 입력·출력
비트스트림, 명령, 메트릭과 추론 메타데이터는 프레임 데이터와 구분하며 호스트 메모리에
존재할 수 있다. 단, 어떤 메타데이터에도 전체 프레임 픽셀을 포함하지 않는다.

**근거**: 파일·네트워크 입출력은 일반적으로 호스트 비트스트림을 사용하며 이는 금지된
GPU → CPU → GPU 전체 프레임 왕복과 다르다. 경계를 명시하면 잘못된 무복사 주장과 과도한
범위를 피할 수 있다.

**검토한 대안**: 모든 압축 바이트까지 GPU 상주시키는 방안은 v1 가치에 필요하지 않고
mux 및 I/O 호환성을 불필요하게 제한한다.
