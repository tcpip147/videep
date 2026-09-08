from __future__ import annotations

from typing import Any


class PassthroughAlgorithm:
    contract_version = "1.0"

    def validate(self, capabilities: Any) -> None:
        if not capabilities.supports_zero_copy():
            raise ValueError("zero-copy capability is required")

    def initialize(self, context: Any) -> None:
        self.context = context

    def process(self, frame_view: Any) -> Any:
        return frame_view

    def close(self) -> None:
        pass


class PreprocessAlgorithm(PassthroughAlgorithm):
    role = "preprocess"


class InferenceAlgorithm(PassthroughAlgorithm):
    role = "inference"


class PostprocessAlgorithm(PassthroughAlgorithm):
    role = "postprocess"


preprocess = PassthroughAlgorithm
inference = PassthroughAlgorithm
postprocess = PassthroughAlgorithm
