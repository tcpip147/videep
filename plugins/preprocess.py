"""사용자 전처리 플러그인.

`process` 함수의 본문을 수정한다. 전체 프레임을 CPU/NumPy로 변환하지 말고
`frame`의 DLPack 인터페이스를 지원하는 GPU 라이브러리에서 직접 사용해야 한다.
"""

from videep.algorithms.contracts import AlgorithmContext, AlgorithmRole
from videep.algorithms.view import FrameView


def process(frame: FrameView) -> None:
    """GPU 상주 프레임을 전처리한다. 기본 구현은 아무 변경 없이 통과시킨다."""
    # 예: tensor = gpu_library.from_dlpack(frame)
    # 이 함수가 반환되기 전에 GPU 작업을 전달한 스트림에 등록해야 한다.
    del frame


class Plugin:
    role = AlgorithmRole.PREPROCESS
    contract_version = "1.0"

    def validate(self, capabilities: object) -> None:
        del capabilities

    def initialize(self, context: AlgorithmContext) -> None:
        self.context = context

    def process(self, frame_view: FrameView) -> None:
        process(frame_view)

    def close(self) -> None:
        pass
