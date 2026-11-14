"""``KisQuoteTransportConfig`` — fail-closed boot config for the KIS 모의투자 QUOTE intake (TOS"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from tos_runtime.transport.endpoint import real_host_problem

__all__ = [
    "KisQuoteTransportConfig",
    "KisQuoteTransportConfigError",
    "load_kis_quote_transport_config",
    "read_declared_instrument",
]

_QUOTE_TR_ID_PATTERN = re.compile(r"^FH[A-Z]{3}\d{8}$")

_TBD_STR = "TBD"


class KisQuoteTransportConfigError(Exception):
    """The KIS QUOTE transport config is missing, malformed, still named-TBD, or names an"""


@dataclass(frozen=True)
class KisQuoteTransportConfig:
    """The fully-valued, fail-closed-loaded KIS QUOTE transport config (module docstring)."""

    endpoint_rest_base: str
    quote_path: str
    token_path: str
    tr_id: str
    instrument: str
    market_div_code: str
    field_mapping: Mapping[str, str]
    source_id: str
    token_reissue_min_interval_s: int
    request_timeout_s: float
    allow_plaintext_for_tests: bool
    app_key_min_request_interval_ms: int
    app_key_request_wait_budget_ms: int


def _require_present(raw: Any, field: str, path: Path) -> Any:
    if not isinstance(raw, dict) or field not in raw:
        raise KisQuoteTransportConfigError(
            f"{path}: KIS QUOTE transport config missing entry {field!r} — refusing to start"
        )
    value = raw[field]
    if value is None:
        raise KisQuoteTransportConfigError(
            f"{path}: {field!r} is still null (named-TBD) — refusing to start until an "
            "operator attests a concrete value"
        )
    return value


def _require_str(raw: Any, field: str, path: Path) -> str:
    value = _require_present(raw, field, path)
    if not isinstance(value, str) or not value:
        raise KisQuoteTransportConfigError(
            f"{path}: {field!r} must be a non-empty string, got {value!r}"
        )
    if value == _TBD_STR:
        raise KisQuoteTransportConfigError(
            f"{path}: {field!r} is still the template placeholder {_TBD_STR!r} — "
            "operator-fill before activation, never a value this loader treats as concrete"
        )
    return value


def _require_int(raw: Any, field: str, path: Path) -> int:
    value = _require_present(raw, field, path)
    if isinstance(value, bool) or not isinstance(value, int):
        raise KisQuoteTransportConfigError(
            f"{path}: {field!r} must be an int, got {value!r}"
        )
    return value


def _require_positive_int(raw: Any, field: str, path: Path) -> int:
    value = _require_int(raw, field, path)
    if value <= 0:
        raise KisQuoteTransportConfigError(
            f"{path}: {field} must be positive, got {value!r}"
        )
    return value


def _require_positive_float(raw: Any, field: str, path: Path) -> float:
    value = _require_present(raw, field, path)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise KisQuoteTransportConfigError(
            f"{path}: {field!r} must be a number, got {value!r}"
        )
    result = float(value)
    if result <= 0:
        raise KisQuoteTransportConfigError(
            f"{path}: {field} must be positive, got {result!r}"
        )
    return result


def _require_bool(raw: Any, field: str, path: Path) -> bool:
    value = _require_present(raw, field, path)
    if not isinstance(value, bool):
        raise KisQuoteTransportConfigError(
            f"{path}: {field!r} must be a bool, got {value!r}"
        )
    return value


def _require_field_mapping(raw: Any, path: Path) -> dict[str, str]:
    block = _require_present(raw, "field_mapping", path)
    if not isinstance(block, dict) or not block:
        raise KisQuoteTransportConfigError(
            f"{path}: 'field_mapping' must be a non-empty mapping, got {block!r} — an empty "
            "mapping would admit no field at all, almost certainly a misfill (mirrors "
            "critical_input_policy.yaml's own empty-fields refusal)"
        )
    result: dict[str, str] = {}
    for key, value in block.items():
        if not isinstance(key, str) or not key:
            raise KisQuoteTransportConfigError(
                f"{path}: 'field_mapping' has a non-string or empty KIS wire field key {key!r}"
            )
        if not isinstance(value, str) or not value:
            raise KisQuoteTransportConfigError(
                f"{path}: field_mapping[{key!r}] is still null (named-TBD) or not a non-empty "
                "string — refusing to start until an operator attests a concrete CIP field_key"
            )
        if value == _TBD_STR:
            raise KisQuoteTransportConfigError(
                f"{path}: field_mapping[{key!r}] is still the template placeholder "
                f"{_TBD_STR!r} — operator-fill before activation"
            )
        result[key] = value
    return result


def _validate_tr_id(value: str, path: Path) -> str:
    if not _QUOTE_TR_ID_PATTERN.match(value):
        raise KisQuoteTransportConfigError(
            f"{path}: tr_id={value!r} does not match the measured KIS quotations TR id shape "
            "('FH' + 3 letters + 8 digits, e.g. FHKST01010100 — module docstring) — refusing "
            "to start"
        )
    return value


def _validate_endpoint(
    endpoint_rest_base: str,
    *,
    instance_mock_rest_base: str,
    instance_real_rest_base: str,
    allow_plaintext_for_tests: bool,
    path: Path,
) -> None:
    """Same host-seal shape as ``kis_mock.config._validate_endpoint`` (module docstring). The"""
    if instance_real_rest_base is None:
        raise KisQuoteTransportConfigError(
            "REAL rest_base must be known (instance_real_rest_base was None) to be excluded — "
            "a caller that cannot state the REAL_PROD host cannot honestly prove this config "
            "excludes it"
        )
    problem = real_host_problem(
        endpoint_rest_base,
        instance_mock_rest_base=instance_mock_rest_base,
        instance_real_rest_base=instance_real_rest_base,
    )
    if problem is not None:
        raise KisQuoteTransportConfigError(f"{path}: {problem}")
    if endpoint_rest_base != instance_mock_rest_base:
        raise KisQuoteTransportConfigError(
            f"{path}: endpoint_rest_base={endpoint_rest_base!r} does not byte-exact match the "
            f"INSTANCE MOCK_VTS document's rest_base {instance_mock_rest_base!r} — a config "
            "value cannot invent its own broker host"
        )
    scheme = urlsplit(endpoint_rest_base).scheme
    if scheme == "http":
        if not allow_plaintext_for_tests:
            raise KisQuoteTransportConfigError(
                f"{path}: endpoint_rest_base={endpoint_rest_base!r} uses http:// but "
                "allow_plaintext_for_tests is false — plaintext is a test-only escape hatch"
            )
    elif scheme != "https":
        raise KisQuoteTransportConfigError(
            f"{path}: endpoint_rest_base={endpoint_rest_base!r} has unsupported scheme "
            f"{scheme!r} — only http (test-only) and https are supported"
        )


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise KisQuoteTransportConfigError(
            f"KIS QUOTE transport config file not found: {path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise KisQuoteTransportConfigError(
            f"KIS QUOTE transport config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise KisQuoteTransportConfigError(
            f"KIS QUOTE transport config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise KisQuoteTransportConfigError(
            f"KIS QUOTE transport config file must be a top-level mapping: {path}"
        )
    return raw


def read_declared_instrument(path: Path) -> str | None:
    """This document's own ``instrument`` leaf, or ``None`` when the document does not exist."""
    if not path.is_file():
        return None
    return _require_str(_read_yaml_mapping(path), "instrument", path)


def load_kis_quote_transport_config(
    path: Path,
    *,
    instance_mock_rest_base: str,
    instance_real_rest_base: str,
) -> KisQuoteTransportConfig:
    """Load + fail-closed-validate the KIS QUOTE transport config from ``path``."""
    raw = _read_yaml_mapping(path)

    allow_plaintext_for_tests = _require_bool(raw, "allow_plaintext_for_tests", path)
    endpoint_rest_base = _require_str(raw, "endpoint_rest_base", path)
    _validate_endpoint(
        endpoint_rest_base,
        instance_mock_rest_base=instance_mock_rest_base,
        instance_real_rest_base=instance_real_rest_base,
        allow_plaintext_for_tests=allow_plaintext_for_tests,
        path=path,
    )

    quote_path = _require_str(raw, "quote_path", path)
    token_path = _require_str(raw, "token_path", path)
    tr_id = _validate_tr_id(_require_str(raw, "tr_id", path), path)
    instrument = _require_str(raw, "instrument", path)
    market_div_code = _require_str(raw, "market_div_code", path)
    field_mapping = _require_field_mapping(raw, path)
    source_id = _require_str(raw, "source_id", path)
    token_reissue_min_interval_s = _require_positive_int(
        raw, "token_reissue_min_interval_s", path
    )
    request_timeout_s = _require_positive_float(raw, "request_timeout_s", path)
    app_key_min_request_interval_ms = _require_positive_int(
        raw, "app_key_min_request_interval_ms", path
    )
    app_key_request_wait_budget_ms = _require_positive_int(
        raw, "app_key_request_wait_budget_ms", path
    )

    return KisQuoteTransportConfig(
        endpoint_rest_base=endpoint_rest_base,
        quote_path=quote_path,
        token_path=token_path,
        tr_id=tr_id,
        instrument=instrument,
        market_div_code=market_div_code,
        field_mapping=field_mapping,
        source_id=source_id,
        token_reissue_min_interval_s=token_reissue_min_interval_s,
        request_timeout_s=request_timeout_s,
        allow_plaintext_for_tests=allow_plaintext_for_tests,
        app_key_min_request_interval_ms=app_key_min_request_interval_ms,
        app_key_request_wait_budget_ms=app_key_request_wait_budget_ms,
    )
