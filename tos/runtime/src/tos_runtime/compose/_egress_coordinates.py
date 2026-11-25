"""Operator-configured egress coordinates + capsule-terminus stand-in"""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import yaml

from tos_runtime._named_tbd import reject_named_tbd
from tos_runtime.compose._types import ConstructionConfig

__all__ = [
    "EgressCoordinateConfigError",
    "EgressCoordinatesConfig",
    "load_egress_coordinates",
]

_ENVIRONMENT_LABEL_TOKEN = "{environment_label}"


class EgressCoordinateConfigError(Exception):
    """Raised when the egress-coordinates config is missing, malformed,"""


@dataclass(frozen=True)
class EgressCoordinatesConfig:
    """The 8 ``EgressCoordinateSet`` authorized-coordinate literals plus"""

    endpoint: str
    action: str
    method: str
    route_identity: str
    credential_generation: int
    broker_session_generation: int
    egress_generation: int
    active_principal: str
    capsule_terminus_fields: tuple[str, ...]


def _require_block(raw: Any, field: str, path: Path) -> dict:
    block = raw.get(field) if isinstance(raw, dict) else None
    if not isinstance(block, dict):
        raise EgressCoordinateConfigError(
            f"{path}: egress-coordinates config missing a mapping entry "
            f"for {field!r} — refusing to start"
        )
    return block


def _require_str(raw: Any, field: str, path: Path) -> str:
    block = _require_block(raw, field, path)
    value = block.get("value")
    if not isinstance(value, str) or not value:
        raise EgressCoordinateConfigError(
            f"{path}: {field!r}.value is still null (named-TBD), empty, or "
            "not a string — refusing to start until an operator attests a "
            "concrete value"
        )
    reject_named_tbd(
        value,
        field=f"{field}.value",
        context=str(path),
        error_cls=EgressCoordinateConfigError,
    )
    return value


def _require_int(raw: Any, field: str, path: Path) -> int:
    block = _require_block(raw, field, path)
    value = block.get("value")
    if isinstance(value, bool) or not isinstance(value, int):
        raise EgressCoordinateConfigError(
            f"{path}: {field!r}.value is still null (named-TBD) or not an "
            "int — refusing to start until an operator attests a concrete "
            "value"
        )
    return value


def load_egress_coordinates(
    path: Path, *, environment_label: str
) -> EgressCoordinatesConfig:
    """Load + fail-closed-validate the egress-coordinates config from"""
    if not path.is_file():
        raise EgressCoordinateConfigError(
            f"egress-coordinates config file not found: {path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EgressCoordinateConfigError(
            f"egress-coordinates config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise EgressCoordinateConfigError(
            f"egress-coordinates config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise EgressCoordinateConfigError(
            f"egress-coordinates config file must be a top-level mapping: {path}"
        )

    endpoint = _require_str(raw, "endpoint", path)
    action = _require_str(raw, "action", path)
    method = _require_str(raw, "method", path)
    route_identity = _require_str(raw, "route_identity", path)
    credential_generation = _require_int(raw, "credential_generation", path)
    broker_session_generation = _require_int(raw, "broker_session_generation", path)
    egress_generation = _require_int(raw, "egress_generation", path)
    active_principal = _require_str(raw, "active_principal", path).replace(
        _ENVIRONMENT_LABEL_TOKEN, environment_label
    )

    terminus_block = _require_block(raw, "capsule_terminus_fields", path)
    terminus_value = terminus_block.get("value")
    if (
        not isinstance(terminus_value, list)
        or not terminus_value
        or not all(isinstance(name, str) and name for name in terminus_value)
    ):
        raise EgressCoordinateConfigError(
            f"{path}: 'capsule_terminus_fields.value' is still null "
            "(named-TBD), empty, or not a non-empty list of strings — "
            "refusing to start"
        )
    known_fields = {f.name for f in fields(ConstructionConfig)}
    unknown = [name for name in terminus_value if name not in known_fields]
    if unknown:
        raise EgressCoordinateConfigError(
            f"{path}: 'capsule_terminus_fields.value' names field(s) not "
            f"present on ConstructionConfig: {unknown!r} — refusing to start"
        )

    return EgressCoordinatesConfig(
        endpoint=endpoint,
        action=action,
        method=method,
        route_identity=route_identity,
        credential_generation=credential_generation,
        broker_session_generation=broker_session_generation,
        egress_generation=egress_generation,
        active_principal=active_principal,
        capsule_terminus_fields=tuple(terminus_value),
    )
