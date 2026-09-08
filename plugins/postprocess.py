"""사용자 후처리 플러그인.

`process` 함수에서 추론 결과를 GPU 상주 프레임에 반영하거나 메타데이터를 계산한다.
프레임 뷰는 함수 호출 범위 밖에 저장할 수 없다.
"""

from videep.algorithms.contracts import AlgorithmContext, AlgorithmRole
from videep.algorithms.view import FrameView


def process(frame: FrameView) -> None:
    """GPU 상주 프레임을 후처리한다. 기본 구현은 아무 변경 없이 통과시킨다."""
    del frame


class Plugin:
    role = AlgorithmRole.POSTPROCESS
    contract_version = "1.0"

    def validate(self, capabilities: object) -> None:
        del capabilities

    def initialize(self, context: AlgorithmContext) -> None:
        self.context = context

    def process(self, frame_view: FrameView) -> None:
        process(frame_view)

    def close(self) -> None:
        pass
