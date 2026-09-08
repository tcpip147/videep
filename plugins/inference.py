"""사용자 추론 플러그인.

모델 로딩은 `Plugin.initialize`, 프레임별 추론은 최상위 `process` 함수를 수정한다.
GPU 리소스 소유권을 보관하거나 전체 프레임을 CPU로 복사해서는 안 된다.
"""

from videep.algorithms.contracts import AlgorithmContext, AlgorithmRole
from videep.algorithms.view import FrameView


def process(frame: FrameView) -> None:
    """GPU 상주 프레임에 추론을 수행한다. 기본 구현은 아무 변경 없이 통과시킨다."""
    del frame


class Plugin:
    role = AlgorithmRole.INFERENCE
    contract_version = "1.0"

    def validate(self, capabilities: object) -> None:
        del capabilities

    def initialize(self, context: AlgorithmContext) -> None:
        self.context = context
        # 사용자 모델과 GPU 실행 컨텍스트를 여기에서 준비한다.

    def process(self, frame_view: FrameView) -> None:
        process(frame_view)

    def close(self) -> None:
        # 사용자 모델 리소스를 여기에서 정리한다.
        pass
