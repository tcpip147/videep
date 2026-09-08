from __future__ import annotations

from videep.algorithms.contracts import AlgorithmRole
from videep.algorithms.loader import validate_component
from videep.algorithms.view import scoped_frame_view


class _Exporter:
    def __dlpack__(self, **kwargs: object) -> object:
        assert kwargs["copy"] is False
        assert kwargs["stream"] == 9
        return object()


class _Stage:
    contract_version = "1.0"

    def __init__(self, role: AlgorithmRole, marker: str) -> None:
        self.role = role
        self.marker = marker

    def validate(self, capabilities: object) -> None:
        pass

    def initialize(self, context: object) -> None:
        pass

    def process(self, frame_view: object) -> object:
        frame_view.__dlpack__()
        return self.marker

    def close(self) -> None:
        pass


def test_each_algorithm_role_can_be_replaced_independently() -> None:
    stages = {role: validate_component(_Stage(role, role.value), role) for role in AlgorithmRole}
    replacement = validate_component(
        _Stage(AlgorithmRole.INFERENCE, "replacement"), AlgorithmRole.INFERENCE
    )
    stages[AlgorithmRole.INFERENCE] = replacement

    with scoped_frame_view(_Exporter(), consumer_stream=9) as view:
        results = [stage.process(view) for stage in stages.values()]

    assert results == ["preprocess", "replacement", "postprocess"]
