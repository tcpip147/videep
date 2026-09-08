"""명시적인 ``module:object`` 알고리즘 로더."""

from __future__ import annotations

import importlib
import inspect
from typing import Any

from .contracts import (
    CONTRACT_VERSION,
    AlgorithmComponent,
    AlgorithmRole,
    contract_major,
    contract_minor,
)


class AlgorithmLoadError(RuntimeError):
    """알고리즘 참조 또는 계약 검증이 실패했다."""


_METHOD_ARITY = {"validate": 1, "initialize": 1, "close": 0}


def _normalize_role(role: AlgorithmRole | str) -> AlgorithmRole:
    try:
        return AlgorithmRole(role)
    except ValueError as exc:
        raise AlgorithmLoadError(f"지원하지 않는 알고리즘 역할: {role!r}") from exc


def _check_signature(component: object, method_name: str, arity: int) -> None:
    method = getattr(component, method_name, None)
    if not callable(method):
        raise AlgorithmLoadError(f"필수 수명 주기 메서드가 없습니다: {method_name}")
    try:
        signature = inspect.signature(method)
        signature.bind(*([object()] * arity))
    except (TypeError, ValueError) as exc:
        raise AlgorithmLoadError(
            f"{method_name} 메서드의 호출 시그니처가 계약과 다릅니다: 인수 {arity}개가 필요합니다"
        ) from exc


def validate_component(component: object, expected_role: AlgorithmRole | str) -> AlgorithmComponent:
    """구성요소의 역할, 버전 및 호출 시그니처를 시작 전에 검증한다."""

    role = _normalize_role(expected_role)
    declared_role = getattr(component, "role", None)
    if not isinstance(declared_role, (str, AlgorithmRole)):
        raise AlgorithmLoadError(f"유효한 role 선언이 없습니다: {declared_role!r}")
    try:
        actual_role = AlgorithmRole(declared_role)
    except (TypeError, ValueError) as exc:
        raise AlgorithmLoadError(f"유효한 role 선언이 없습니다: {declared_role!r}") from exc
    if actual_role is not role:
        raise AlgorithmLoadError(
            f"알고리즘 역할 불일치: 필요={role.value}, 실제={actual_role.value}"
        )

    version = getattr(component, "contract_version", None)
    if not isinstance(version, str):
        raise AlgorithmLoadError(f"유효한 contract_version 선언이 없습니다: {version!r}")
    try:
        actual_major = contract_major(version)
        expected_major = contract_major(CONTRACT_VERSION)
    except ValueError as exc:
        raise AlgorithmLoadError(str(exc)) from exc
    if actual_major != expected_major:
        raise AlgorithmLoadError(
            f"알고리즘 계약 주 버전 불일치: 필요={CONTRACT_VERSION}, 실제={version}"
        )

    for method_name, arity in _METHOD_ARITY.items():
        _check_signature(component, method_name, arity)
    _check_signature(component, "process", 2 if contract_minor(version) >= 1 else 1)
    return component  # type: ignore[return-value]


def load_algorithm(reference: str, expected_role: AlgorithmRole | str) -> AlgorithmComponent:
    """참조를 import하고 필요하면 클래스를 인스턴스화한 뒤 계약을 검증한다."""

    if reference.count(":") != 1:
        raise AlgorithmLoadError(
            f"알고리즘 참조는 'module:object' 형식이어야 합니다: {reference!r}"
        )
    module_name, object_name = reference.split(":", maxsplit=1)
    if not module_name or not object_name or "." in object_name:
        raise AlgorithmLoadError(
            f"알고리즘 참조는 'module:object' 형식이어야 합니다: {reference!r}"
        )
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        raise AlgorithmLoadError(f"알고리즘 모듈을 가져올 수 없습니다: {module_name}") from exc
    try:
        candidate: Any = getattr(module, object_name)
    except AttributeError as exc:
        raise AlgorithmLoadError(f"알고리즘 객체를 찾을 수 없습니다: {reference}") from exc

    try:
        component = candidate() if inspect.isclass(candidate) else candidate
    except Exception as exc:
        raise AlgorithmLoadError(f"알고리즘 객체 생성에 실패했습니다: {reference}") from exc
    return validate_component(component, expected_role)
