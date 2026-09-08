from __future__ import annotations

import sys
from types import ModuleType

import pytest

from videep.algorithms.contracts import AlgorithmRole
from videep.algorithms.loader import AlgorithmLoadError, load_algorithm


class GoodAlgorithm:
    role = "preprocess"
    contract_version = "1.2"

    def validate(self, capabilities: object) -> None:
        self.capabilities = capabilities

    def initialize(self, context: object) -> None:
        self.context = context

    def process(self, frame_view: object, artifacts: object) -> object:
        return frame_view

    def close(self) -> None:
        pass


@pytest.fixture
def algorithm_module() -> str:
    name = "tests_dynamic_algorithm"
    module = ModuleType(name)
    module.Component = GoodAlgorithm
    sys.modules[name] = module
    yield name
    sys.modules.pop(name, None)


def test_module_object_class_is_loaded_and_validated(algorithm_module: str) -> None:
    component = load_algorithm(f"{algorithm_module}:Component", AlgorithmRole.PREPROCESS)
    assert isinstance(component, GoodAlgorithm)


@pytest.mark.parametrize("reference", ["missing_separator", "a:b:c", ":object"])
def test_invalid_reference_reports_cause(reference: str) -> None:
    with pytest.raises(AlgorithmLoadError, match="module:object"):
        load_algorithm(reference, AlgorithmRole.PREPROCESS)


def test_role_mismatch_is_rejected(algorithm_module: str) -> None:
    with pytest.raises(AlgorithmLoadError, match="역할 불일치"):
        load_algorithm(f"{algorithm_module}:Component", AlgorithmRole.INFERENCE)


def test_major_contract_version_mismatch_is_rejected(algorithm_module: str) -> None:
    sys.modules[algorithm_module].Component.contract_version = "2.0"
    try:
        with pytest.raises(AlgorithmLoadError, match="주 버전 불일치"):
            load_algorithm(f"{algorithm_module}:Component", AlgorithmRole.PREPROCESS)
    finally:
        sys.modules[algorithm_module].Component.contract_version = "1.2"


def test_lifecycle_signature_is_checked(algorithm_module: str) -> None:
    original_process = GoodAlgorithm.process
    sys.modules[algorithm_module].Component.process = lambda self: None
    try:
        with pytest.raises(AlgorithmLoadError, match="process.*시그니처"):
            load_algorithm(f"{algorithm_module}:Component", AlgorithmRole.PREPROCESS)
    finally:
        sys.modules[algorithm_module].Component.process = original_process
