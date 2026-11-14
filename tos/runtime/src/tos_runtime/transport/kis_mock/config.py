"""``KisMockTransportConfig`` — fail-closed boot config for the KIS MOCK stock transport"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

import yaml

from tos_runtime.transport.endpoint import real_host_problem

__all__ = [
    "DYNAMIC_FIELD_SOURCES",
    "KIS_ORDER_CASH_WIRE_FIELDS",
    "KisMockTransportConfig",
    "KisMockTransportConfigError",
    "load_kis_mock_transport_config",
]

_VALID_MODES = ("dry_run", "live")

_FORBIDDEN_TR_PREFIXES = ("T", "STTN", "CTF")

_TR_ID_PATTERN = re.compile(r"^V[A-Z]{3}\d{4}[A-Z]$")

DYNAMIC_FIELD_SOURCES: frozenset[str] = frozenset(
    {"account", "instrument", "quantity", "price"}
)

KIS_ORDER_CASH_WIRE_FIELDS: frozenset[str] = frozenset(
    {
        "CANO",
        "ACNT_PRDT_CD",
        "PDNO",
        "ORD_DVSN",
        "ORD_QTY",
        "ORD_UNPR",
        "EXCG_ID_DVSN_CD",
        "SLL_TYPE",
        "CNDT_PRIC",
    }
)

_TBD_STR = "TBD"


class KisMockTransportConfigError(Exception):
    """The KIS MOCK transport config is missing, malformed, still named-TBD, or names an"""


@dataclass(frozen=True)
class KisMockTransportConfig:
    """The fully-valued, fail-closed-loaded KIS MOCK transport config (plan §2 결정 1; review"""

    mode: Literal["dry_run", "live"]
    endpoint_rest_base: str
    order_path: str
    token_path: str
    tr_id_buy: str
    tr_id_sell: str
    field_map: Mapping[str, str]
    static_body_fields: Mapping[str, str]
    price_scale: int
    min_send_interval_ms: int
    app_key_request_wait_budget_ms: int
    token_reissue_min_interval_s: int
    request_timeout_s: float
    allow_plaintext_for_tests: bool


def _require_present(raw: Any, field: str, path: Path) -> Any:
    if not isinstance(raw, dict) or field not in raw:
        raise KisMockTransportConfigError(
            f"{path}: KIS MOCK transport config missing entry {field!r} — refusing to start"
        )
    value = raw[field]
    if value is None:
        raise KisMockTransportConfigError(
            f"{path}: {field!r} is still null (named-TBD) — refusing to start until an "
            "operator attests a concrete value"
        )
    return value


def _require_str(raw: Any, field: str, path: Path) -> str:
    value = _require_present(raw, field, path)
    if not isinstance(value, str) or not value:
        raise KisMockTransportConfigError(
            f"{path}: {field!r} must be a non-empty string, got {value!r}"
        )
    if value == _TBD_STR:
        raise KisMockTransportConfigError(
            f"{path}: {field!r} is still the template placeholder {_TBD_STR!r} — "
            "operator-fill before activation, never a value this loader treats as concrete"
        )
    return value


def _require_int(raw: Any, field: str, path: Path) -> int:
    value = _require_present(raw, field, path)
    if isinstance(value, bool) or not isinstance(value, int):
        raise KisMockTransportConfigError(
            f"{path}: {field!r} must be an int, got {value!r}"
        )
    return value


def _require_float(raw: Any, field: str, path: Path) -> float:
    value = _require_present(raw, field, path)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise KisMockTransportConfigError(
            f"{path}: {field!r} must be a number, got {value!r}"
        )
    return float(value)


def _require_bool(raw: Any, field: str, path: Path) -> bool:
    value = _require_present(raw, field, path)
    if not isinstance(value, bool):
        raise KisMockTransportConfigError(
            f"{path}: {field!r} must be a bool, got {value!r}"
        )
    return value


def _require_str_mapping(
    raw: Any, field: str, path: Path, *, allow_empty_value: bool = False
) -> dict[str, str]:
    """Require ``raw[field]`` to be a non-empty mapping of non-empty string keys to string"""
    block = _require_present(raw, field, path)
    if not isinstance(block, dict) or not block:
        raise KisMockTransportConfigError(
            f"{path}: {field!r} must be a non-empty mapping, got {block!r}"
        )
    result: dict[str, str] = {}
    for key, value in block.items():
        if not isinstance(key, str) or not key:
            raise KisMockTransportConfigError(
                f"{path}: {field!r} has a non-string or empty key {key!r}"
            )
        if value is None or not isinstance(value, str):
            raise KisMockTransportConfigError(
                f"{path}: {field!r}[{key!r}] is still null (named-TBD) or not a string — "
                "refusing to start until an operator attests a concrete value"
            )
        if not value and not allow_empty_value:
            raise KisMockTransportConfigError(
                f"{path}: {field!r}[{key!r}] is empty — refusing to start until an operator "
                "attests a concrete value"
            )
        if value == _TBD_STR:
            raise KisMockTransportConfigError(
                f"{path}: {field!r}[{key!r}] is still the template placeholder {_TBD_STR!r} — "
                "operator-fill before activation"
            )
        result[key] = value
    return result


def _validate_tr_id(value: str, field: str, path: Path) -> str:
    for forbidden in _FORBIDDEN_TR_PREFIXES:
        if value.startswith(forbidden):
            raise KisMockTransportConfigError(
                f"{path}: {field}={value!r} carries the {forbidden!r} prefix — that is a "
                "real-order (or real-night) TR id convention (module docstring); this MOCK-only "
                "transport admits only 'V'-prefixed TR ids"
            )
    if not _TR_ID_PATTERN.match(value):
        raise KisMockTransportConfigError(
            f"{path}: {field}={value!r} does not match the KIS mock order TR id shape "
            "('V' + 3 letters + 4 digits + 1 letter, e.g. VTTC0012U — module docstring, "
            "review F7) — refusing to start"
        )
    return value


def _validate_field_map_and_static_fields(
    field_map: dict[str, str], static_body_fields: dict[str, str], path: Path
) -> tuple[dict[str, str], dict[str, str]]:
    """(review F1) The two configs together must cover exactly the nine KIS wire fields."""
    unknown = sorted(set(field_map) - DYNAMIC_FIELD_SOURCES)
    if unknown:
        raise KisMockTransportConfigError(
            f"{path}: field_map names unrecognized dynamic source(s) {unknown!r} — only "
            f"{sorted(DYNAMIC_FIELD_SOURCES)!r} are recognized kernel-side values"
        )
    combined = list(field_map.values()) + list(static_body_fields.keys())
    if len(combined) != len(set(combined)):
        raise KisMockTransportConfigError(
            f"{path}: field_map and static_body_fields map two different sources onto the "
            f"same KIS wire field name (field_map={field_map!r}, "
            f"static_body_fields={static_body_fields!r}) — a body cannot carry the same key "
            "twice"
        )
    present = frozenset(combined)
    if present != KIS_ORDER_CASH_WIRE_FIELDS:
        missing = sorted(KIS_ORDER_CASH_WIRE_FIELDS - present)
        unexpected = sorted(present - KIS_ORDER_CASH_WIRE_FIELDS)
        raise KisMockTransportConfigError(
            f"{path}: field_map + static_body_fields do not cover exactly the nine KIS "
            f"order_cash fields (N-17 memo) — missing={missing!r} unexpected={unexpected!r}"
        )
    return field_map, static_body_fields


def _validate_endpoint(
    endpoint_rest_base: str,
    *,
    instance_mock_rest_base: str,
    instance_real_rest_base: str,
    allow_plaintext_for_tests: bool,
    path: Path,
) -> None:
    if instance_real_rest_base is None:
        raise KisMockTransportConfigError(
            "REAL rest_base must be known (instance_real_rest_base was None) to be excluded — "
            "a caller that cannot state the REAL_PROD host cannot honestly prove this config "
            "excludes it (review F3)"
        )
    problem = real_host_problem(
        endpoint_rest_base,
        instance_mock_rest_base=instance_mock_rest_base,
        instance_real_rest_base=instance_real_rest_base,
    )
    if problem is not None:
        raise KisMockTransportConfigError(f"{path}: {problem}")
    if endpoint_rest_base != instance_mock_rest_base:
        raise KisMockTransportConfigError(
            f"{path}: endpoint_rest_base={endpoint_rest_base!r} does not byte-exact match the "
            f"INSTANCE MOCK_VTS document's rest_base {instance_mock_rest_base!r} — a config "
            "value cannot invent its own broker host (decision 5, one source of truth)"
        )
    scheme = urlsplit(endpoint_rest_base).scheme
    if scheme == "http":
        if not allow_plaintext_for_tests:
            raise KisMockTransportConfigError(
                f"{path}: endpoint_rest_base={endpoint_rest_base!r} uses http:// but "
                "allow_plaintext_for_tests is false — plaintext is a test-only escape hatch"
            )
    elif scheme != "https":
        raise KisMockTransportConfigError(
            f"{path}: endpoint_rest_base={endpoint_rest_base!r} has unsupported scheme "
            f"{scheme!r} — only http (test-only) and https are supported"
        )


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    """Read + parse ``path`` as a top-level YAML mapping — the first three fail-closed checks"""
    if not path.is_file():
        raise KisMockTransportConfigError(
            f"KIS MOCK transport config file not found: {path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise KisMockTransportConfigError(
            f"KIS MOCK transport config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise KisMockTransportConfigError(
            f"KIS MOCK transport config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise KisMockTransportConfigError(
            f"KIS MOCK transport config file must be a top-level mapping: {path}"
        )
    return raw


def _require_positive_int(raw: Any, field: str, path: Path) -> int:
    value = _require_int(raw, field, path)
    if value <= 0:
        raise KisMockTransportConfigError(
            f"{path}: {field} must be positive, got {value!r}"
        )
    return value


def _require_positive_float(raw: Any, field: str, path: Path) -> float:
    value = _require_float(raw, field, path)
    if value <= 0:
        raise KisMockTransportConfigError(
            f"{path}: {field} must be positive, got {value!r}"
        )
    return value


def load_kis_mock_transport_config(
    path: Path,
    *,
    instance_mock_rest_base: str,
    instance_real_rest_base: str,
    codec_bound: bool = False,
) -> KisMockTransportConfig:
    """Load + fail-closed-validate the KIS MOCK transport config from ``path``."""
    raw = _read_yaml_mapping(path)

    mode = _require_str(raw, "mode", path)
    if mode not in _VALID_MODES:
        raise KisMockTransportConfigError(
            f"{path}: mode={mode!r} must be one of {_VALID_MODES!r}"
        )
    if mode == "live" and codec_bound is not True:
        raise KisMockTransportConfigError(
            "live mode requires the T2 seal-codec binding (plan §4 T2) — the compose root "
            "must wire KisWireCodecDigest and pass codec_bound=True to attest it; dry_run "
            "only otherwise (review disposition F1/F6 — see this module's own docstring)"
        )

    allow_plaintext_for_tests = _require_bool(raw, "allow_plaintext_for_tests", path)
    endpoint_rest_base = _require_str(raw, "endpoint_rest_base", path)
    _validate_endpoint(
        endpoint_rest_base,
        instance_mock_rest_base=instance_mock_rest_base,
        instance_real_rest_base=instance_real_rest_base,
        allow_plaintext_for_tests=allow_plaintext_for_tests,
        path=path,
    )

    order_path = _require_str(raw, "order_path", path)
    token_path = _require_str(raw, "token_path", path)
    tr_id_buy = _validate_tr_id(_require_str(raw, "tr_id_buy", path), "tr_id_buy", path)
    tr_id_sell = _validate_tr_id(
        _require_str(raw, "tr_id_sell", path), "tr_id_sell", path
    )
    field_map, static_body_fields = _validate_field_map_and_static_fields(
        _require_str_mapping(raw, "field_map", path),
        _require_str_mapping(raw, "static_body_fields", path, allow_empty_value=True),
        path,
    )

    price_scale = _require_positive_int(raw, "price_scale", path)
    min_send_interval_ms = _require_positive_int(raw, "min_send_interval_ms", path)
    app_key_request_wait_budget_ms = _require_positive_int(
        raw, "app_key_request_wait_budget_ms", path
    )
    token_reissue_min_interval_s = _require_positive_int(
        raw, "token_reissue_min_interval_s", path
    )
    request_timeout_s = _require_positive_float(raw, "request_timeout_s", path)

    return KisMockTransportConfig(
        mode=mode,  # type: ignore[arg-type]  # narrowed by the membership check above
        endpoint_rest_base=endpoint_rest_base,
        order_path=order_path,
        token_path=token_path,
        tr_id_buy=tr_id_buy,
        tr_id_sell=tr_id_sell,
        field_map=field_map,
        static_body_fields=static_body_fields,
        price_scale=price_scale,
        min_send_interval_ms=min_send_interval_ms,
        app_key_request_wait_budget_ms=app_key_request_wait_budget_ms,
        token_reissue_min_interval_s=token_reissue_min_interval_s,
        request_timeout_s=request_timeout_s,
        allow_plaintext_for_tests=allow_plaintext_for_tests,
    )
